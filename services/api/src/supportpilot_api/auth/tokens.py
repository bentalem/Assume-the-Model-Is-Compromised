"""Token verification.

Built before any business endpoint exists, so no endpoint can be reached without it
(SP-PLAN-003 §8). Every check below rejects *before* policy evaluation and before any database
access — `TS1-02` asserts there is no database call in the trace of a rejected request.

Trust rules that shape this module:

* The token establishes *who the caller is*. It never establishes what they may do.
* Role and organization claims in the token are a hint at most. Memberships are loaded from the
  database on every request, so a revoked membership takes effect immediately even while an issued
  token still carries the role (`TS1-10`).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from ..errors import unauthenticated

logger = logging.getLogger(__name__)

# Asymmetric signatures only. 'none' and the HMAC family are refused outright: an HMAC token would
# be verifiable with a value an attacker might obtain, and 'none' is not a signature at all.
ALLOWED_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384"})

_JWKS_CACHE_SECONDS = 300
_JWKS_MIN_REFETCH_SECONDS = 10


@dataclass(frozen=True)
class VerifiedToken:
    """The result of verification. Carries identity only — no authority."""

    subject: str
    token_id: str | None
    issued_at: int | None
    expires_at: int | None
    authentication_level: str
    scopes: frozenset[str]

    @property
    def is_mfa(self) -> bool:
        return self.authentication_level == "mfa"


class JwksCache:
    """Caches the realm key set.

    Refetches on an unknown `kid` so key rotation is picked up without a restart (`TS1-09`), but no
    more often than `_JWKS_MIN_REFETCH_SECONDS` — otherwise a stream of tokens with bogus key ids
    would turn into a request amplifier against Keycloak.
    """

    def __init__(self, jwks_url: str, timeout_seconds: float = 5.0) -> None:
        self._url = jwks_url
        self._timeout = timeout_seconds
        self._lock = threading.Lock()
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at = 0.0

    def _fetch(self) -> None:
        response = httpx.get(self._url, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()
        keys = {key["kid"]: key for key in payload.get("keys", []) if "kid" in key}
        if not keys:
            raise ValueError("key set contained no usable keys")
        self._keys = keys
        self._fetched_at = time.monotonic()

    def get(self, kid: str) -> dict[str, Any] | None:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            stale = age > _JWKS_CACHE_SECONDS
            unknown = kid not in self._keys

            if not self._keys or stale or unknown:
                if unknown and not stale and age < _JWKS_MIN_REFETCH_SECONDS:
                    return None
                try:
                    self._fetch()
                except Exception:
                    # A fetch failure is not an authorization decision. If a usable cached key
                    # remains, keep serving it per the configured cache policy
                    # (SP-ARCH-001 §10, "Keycloak unavailable"); otherwise the caller gets None
                    # and the request is rejected.
                    logger.warning("jwks_fetch_failed", exc_info=True)
            return self._keys.get(kid)

    def invalidate(self) -> None:
        with self._lock:
            self._keys = {}
            self._fetched_at = 0.0


class TokenVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks: JwksCache,
        leeway_seconds: int = 30,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks = jwks
        self._leeway = leeway_seconds

    def verify(self, raw_token: str) -> VerifiedToken:
        """Verify a bearer token or raise 401. Never returns a partially-checked result."""
        if not raw_token or raw_token.count(".") != 2:
            raise unauthenticated()

        try:
            header = jwt.get_unverified_header(raw_token)
        except JWTError:
            raise unauthenticated() from None

        algorithm = header.get("alg")
        if algorithm not in ALLOWED_ALGORITHMS:
            # Covers alg=none and any attempt to downgrade to a symmetric algorithm (`TS1-03`).
            logger.info("token_rejected", extra={"reason": "algorithm_not_allowed"})
            raise unauthenticated()

        kid = header.get("kid")
        if not kid:
            raise unauthenticated()

        key = self._jwks.get(kid)
        if key is None:
            logger.info("token_rejected", extra={"reason": "unknown_key_id"})
            raise unauthenticated()

        try:
            claims = jwt.decode(
                raw_token,
                key,
                algorithms=[algorithm],
                issuer=self._issuer,
                audience=self._audience,
                options={
                    "require_exp": True,
                    "require_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_signature": True,
                    "leeway": self._leeway,
                },
            )
        except JWTError:
            # One rejection path for signature, issuer, audience, expiry, and not-before. The caller
            # learns only that the token was refused.
            logger.info("token_rejected", extra={"reason": "claims_or_signature_invalid"})
            raise unauthenticated() from None

        subject = claims.get("sub")
        if not subject or not isinstance(subject, str):
            raise unauthenticated()

        # An access token only. Refusing 'Refresh' and 'ID' stops a token minted for a different
        # purpose from being replayed at the action endpoint (`TS1-08`).
        token_type = claims.get("typ")
        if token_type is not None and token_type not in {"Bearer", "JWT"}:
            logger.info("token_rejected", extra={"reason": "wrong_token_type"})
            raise unauthenticated()

        return VerifiedToken(
            subject=subject,
            token_id=claims.get("jti"),
            issued_at=claims.get("iat"),
            expires_at=claims.get("exp"),
            authentication_level=_authentication_level(claims),
            scopes=frozenset(str(claims.get("scope", "")).split()),
        )


def _authentication_level(claims: dict[str, Any]) -> str:
    """Derive authentication strength from the token's ACR/AMR claims.

    Anything not positively recognised as multi-factor is reported as single factor. Policy decides
    what that is worth; this function does not.
    """
    acr = str(claims.get("acr", ""))
    if acr in {"2", "mfa", "gold"}:
        return "mfa"
    amr = claims.get("amr") or []
    if isinstance(amr, list) and any(str(m).lower() in {"mfa", "otp", "hwk", "sc"} for m in amr):
        return "mfa"
    return "single_factor"


def bearer_from_header(header_value: str | None) -> str:
    """Extract a bearer token, rejecting any other scheme."""
    if not header_value:
        raise unauthenticated()
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthenticated()
    return token.strip()
