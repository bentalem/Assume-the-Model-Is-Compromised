"""Tokens: the user's, which the broker verifies, and the delegated ones it mints.

The broker verifies a user's token the way the API does — signature against Keycloak's published
keys, issuer, audience, expiry, an asymmetric algorithm — and for the same audience, because it is
the API's gateway. It mints one kind of token: ES256, its own issuer, the user as `sub`, the agent
as `act`, a narrow `scope`, a `jti`, and five minutes at most. It verifies its own tokens only when
one comes back to be exchanged again.

No token string is ever logged or returned in an error. Reasons are stable codes.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from jose import jwk, jwt
from jose.exceptions import JWTError

logger = logging.getLogger("supportpilot.broker.tokens")

USER_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384"})
BROKER_ALGORITHM = "ES256"
MAX_LIFETIME_SECONDS = 300
MAX_ACTOR_DEPTH = 4

_JWKS_CACHE_SECONDS = 300
_JWKS_MIN_REFETCH_SECONDS = 10


class TokenRefused(Exception):
    """A token that will not be accepted. `reason` is a stable code; it never carries the token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class UserToken:
    subject: str
    expires_at: int
    acr: str | None


@dataclass(frozen=True)
class DelegatedToken:
    subject: str
    act: dict[str, Any]
    scopes: frozenset[str]
    expires_at: int
    acr: str | None

    @property
    def depth(self) -> int:
        depth, current = 0, self.act
        while isinstance(current, dict):
            depth += 1
            current = current.get("act")
        return depth


class SigningKey:
    """The broker's ES256 key. Mounted to this service only; its public half is published."""

    def __init__(self, private_pem: str) -> None:
        private = serialization.load_pem_private_key(private_pem.encode(), password=None)
        public_der = private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_pem = private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self._private_pem = private_pem
        # A key id derived from the key, so a new key is a new id without anyone choosing one.
        self.kid = base64.urlsafe_b64encode(hashlib.sha256(public_der).digest()[:12]).decode().rstrip("=")
        public = jwk.construct(public_pem, algorithm=BROKER_ALGORITHM).to_dict()
        public.update({"kid": self.kid, "alg": BROKER_ALGORITHM, "use": "sig"})
        self.public_jwk = public

    def jwks(self) -> dict[str, Any]:
        return {"keys": [self.public_jwk]}

    def sign(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._private_pem, algorithm=BROKER_ALGORITHM,
                          headers={"kid": self.kid, "typ": "JWT"})


class Minter:
    def __init__(self, key: SigningKey, issuer: str, audience: str) -> None:
        self._key = key
        self.issuer = issuer
        self.audience = audience

    def mint(
        self,
        *,
        subject: str,
        act: dict[str, Any],
        scopes: frozenset[str],
        lifetime_seconds: int,
        not_after: int | None = None,
        acr: str | None = None,
        now: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return the token and its claims. The claims are for the caller's log; the token is not."""
        issued = int(now if now is not None else time.time())
        expires = issued + min(lifetime_seconds, MAX_LIFETIME_SECONDS)
        if not_after is not None:
            # A re-exchanged token may not outlive the one it was made from.
            expires = min(expires, not_after)
        if expires <= issued:
            raise TokenRefused("subject_token_expired")
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "sub": subject,
            "aud": self.audience,
            "act": act,
            "scope": " ".join(sorted(scopes)),
            "iat": issued,
            "exp": expires,
            "jti": uuid.uuid4().hex,
            "typ": "Bearer",
        }
        if acr:
            claims["acr"] = acr
        return self._key.sign(claims), claims

    def verify_own(self, raw: str) -> DelegatedToken:
        """A token this broker minted, coming back to be exchanged again."""
        try:
            header = jwt.get_unverified_header(raw)
            if header.get("alg") != BROKER_ALGORITHM or header.get("kid") != self._key.kid:
                raise TokenRefused("subject_token_invalid")
            claims = jwt.decode(
                raw, self._key.public_jwk, algorithms=[BROKER_ALGORITHM],
                issuer=self.issuer, audience=self.audience,
                options={"require_aud": True, "require_exp": True, "require_iat": True},
            )
        except JWTError:
            raise TokenRefused("subject_token_invalid") from None
        act = claims.get("act")
        if not isinstance(act, dict) or not isinstance(claims.get("sub"), str):
            raise TokenRefused("subject_token_invalid")
        return DelegatedToken(
            subject=claims["sub"],
            act=act,
            scopes=frozenset(str(claims.get("scope", "")).split()),
            expires_at=int(claims["exp"]),
            acr=_acr(claims),
        )


class KeycloakKeys:
    """Keycloak's published key set: cached, refetched on an unknown key id at most every 10 s."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._lock = threading.Lock()
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at = 0.0

    def get(self, kid: str) -> dict[str, Any] | None:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            if not self._keys or age > _JWKS_CACHE_SECONDS or (
                kid not in self._keys and age >= _JWKS_MIN_REFETCH_SECONDS
            ):
                try:
                    response = httpx.get(self._url, timeout=5)
                    response.raise_for_status()
                    keys = {k["kid"]: k for k in response.json().get("keys", []) if "kid" in k}
                    if keys:
                        self._keys, self._fetched_at = keys, time.monotonic()
                except Exception:  # noqa: BLE001 — a fetch failure is a refusal, never an allow
                    logger.warning("keycloak_jwks_fetch_failed", exc_info=True)
            return self._keys.get(kid)


class UserVerifier:
    def __init__(self, *, issuer: str, audience: str, keys: KeycloakKeys, leeway: int = 30) -> None:
        self.issuer = issuer
        self._audience = audience
        self._keys = keys
        self._leeway = leeway

    def verify(self, raw: str) -> UserToken:
        try:
            header = jwt.get_unverified_header(raw)
        except JWTError:
            raise TokenRefused("user_token_invalid") from None
        algorithm, kid = header.get("alg"), header.get("kid")
        if algorithm not in USER_ALGORITHMS or not kid:
            raise TokenRefused("user_token_invalid")
        key = self._keys.get(kid)
        if key is None:
            raise TokenRefused("user_token_invalid")
        try:
            claims = jwt.decode(
                raw, key, algorithms=[algorithm], issuer=self.issuer, audience=self._audience,
                options={"require_aud": True, "require_exp": True, "require_iat": True,
                         "leeway": self._leeway},
            )
        except JWTError:
            raise TokenRefused("user_token_invalid") from None
        # A user's own token names nobody acting for them. One that does is not a user's token.
        if "act" in claims:
            raise TokenRefused("user_token_invalid")
        if claims.get("typ") not in (None, "Bearer", "JWT"):
            raise TokenRefused("user_token_invalid")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise TokenRefused("user_token_invalid")
        return UserToken(subject=subject, expires_at=int(claims["exp"]), acr=_acr(claims))


def unverified_issuer(raw: str) -> str | None:
    """Which issuer a token names, read only to choose how to verify it."""
    try:
        claims = jwt.get_unverified_claims(raw)
    except JWTError:
        return None
    issuer = claims.get("iss") if isinstance(claims, dict) else None
    return issuer if isinstance(issuer, str) else None


def _acr(claims: dict[str, Any]) -> str | None:
    acr = claims.get("acr")
    return acr if isinstance(acr, str) and len(acr) <= 32 else None
