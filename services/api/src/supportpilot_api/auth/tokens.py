"""Token verification.

Built before any business endpoint exists, so no endpoint can be reached without it
(SP-PLAN-003 §8). Every check below rejects *before* policy evaluation and before any database
access — `TS1-02` asserts there is no database call in the trace of a rejected request.

Trust rules that shape this module:

* The token establishes *who the caller is*. It never establishes what they may do.
* Role and organization claims in the token are a hint at most. Memberships are loaded from the
  database on every request, so a revoked membership takes effect immediately even while an issued
  token still carries the role (`TS1-10`).
* Two issuers are trusted, each with its own rules, and a token is verified only against the issuer
  it names (`IssuerRegistry`). Keycloak's tokens name a user and never carry `act`. The delegation
  broker's tokens name a user *and* the agent acting for them, and always carry `act`. Every issuer
  an API trusts is a key to it, which is why the second one is narrower than the first rather than
  equal to it.
"""

from __future__ import annotations

import logging
import re
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

# An agent name in `act.sub`: a registered profile name, never free text. Bounded so the chain can
# be written to the audit trail and a log line as it is.
_ACTOR_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
# Delegation hops a token may carry. The lab's longest chain is two.
_MAX_ACTOR_DEPTH = 4

# What a token says about `act`. Keycloak's must not carry it; the broker's must.
ACTOR_FORBIDDEN = "forbidden"
ACTOR_REQUIRED = "required"


@dataclass(frozen=True)
class VerifiedToken:
    """The result of verification.

    Carries identity, and for a delegated token a *limit* on authority — never authority itself.
    `subject` is the user. `actor_chain` is empty for a user's own token; for a delegated one it is
    the agents acting for that user, in delegation order: the first is the agent the user delegated
    to, the last is the one making this call. `scopes` is what the token was narrowed to; the policy
    reads it only when `actor_chain` is non-empty, and roles still come from the database.
    """

    subject: str
    token_id: str | None
    issued_at: int | None
    expires_at: int | None
    authentication_level: str
    scopes: frozenset[str]
    actor_chain: tuple[str, ...] = ()

    @property
    def is_mfa(self) -> bool:
        return self.authentication_level == "mfa"

    @property
    def is_delegated(self) -> bool:
        return bool(self.actor_chain)

    @property
    def agent_id(self) -> str | None:
        """The chain as the audit trail records it, or None for a user's own token."""
        return " > ".join(self.actor_chain) if self.actor_chain else None


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
        allowed_algorithms: frozenset[str] = ALLOWED_ALGORITHMS,
        actor: str = ACTOR_FORBIDDEN,
        max_lifetime_seconds: int | None = None,
    ) -> None:
        if not allowed_algorithms <= ALLOWED_ALGORITHMS:
            raise ValueError("an issuer may only narrow the algorithm allowlist, never widen it")
        if actor not in (ACTOR_FORBIDDEN, ACTOR_REQUIRED):
            raise ValueError(f"unknown actor rule {actor!r}")
        self._issuer = issuer
        self._audience = audience
        self._jwks = jwks
        self._leeway = leeway_seconds
        self._algorithms = allowed_algorithms
        self._actor = actor
        self._max_lifetime = max_lifetime_seconds

    @property
    def issuer(self) -> str:
        return self._issuer

    def verify(self, raw_token: str) -> VerifiedToken:
        """Verify a bearer token or raise 401. Never returns a partially-checked result."""
        if not raw_token or raw_token.count(".") != 2:
            raise unauthenticated()

        try:
            header = jwt.get_unverified_header(raw_token)
        except JWTError:
            raise unauthenticated() from None

        algorithm = header.get("alg")
        if algorithm not in self._algorithms:
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
                    # python-jose's audience check runs only when an `aud` claim is present, so
                    # without this a correctly signed token naming no audience at all was accepted
                    # as though it had named this API. verify_aud alone does not cover it.
                    "require_aud": True,
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

        # Who is acting. A user's own token names nobody else; a delegated token must name the
        # agent, and a malformed `act` is a refusal rather than a token treated as the user's own.
        if self._actor == ACTOR_FORBIDDEN:
            if "act" in claims:
                logger.info("token_rejected", extra={"reason": "unexpected_actor"})
                raise unauthenticated()
            actor_chain: tuple[str, ...] = ()
        else:
            actor_chain = _actor_chain(claims.get("act"))
            if not actor_chain:
                logger.info("token_rejected", extra={"reason": "actor_missing_or_malformed"})
                raise unauthenticated()

        # A short-lived issuer's tokens are refused if they claim a longer life than it may mint,
        # whatever `exp` says: a token that outlives its task is authority left lying around.
        if self._max_lifetime is not None and not _short_lived(claims, self._max_lifetime):
            logger.info("token_rejected", extra={"reason": "lifetime_or_jti_invalid"})
            raise unauthenticated()

        return VerifiedToken(
            subject=subject,
            token_id=claims.get("jti"),
            issued_at=claims.get("iat"),
            expires_at=claims.get("exp"),
            authentication_level=_authentication_level(claims),
            scopes=frozenset(str(claims.get("scope", "")).split()),
            actor_chain=actor_chain,
        )


class IssuerRegistry:
    """Verify a token against the one issuer it names, and only that one.

    The issuer is read from the unverified token before any key is fetched, and it chooses the
    verifier — its key set, its algorithms, its rules about `act`. It decides nothing else: the
    chosen verifier checks `iss` again against the signature it verifies, so a token that names one
    issuer and is signed by the other fails there. An issuer that is not registered is refused on
    the same path as every other refusal.
    """

    def __init__(self, verifiers: list[TokenVerifier]) -> None:
        self._by_issuer = {verifier.issuer: verifier for verifier in verifiers}
        if len(self._by_issuer) != len(verifiers):
            raise ValueError("two verifiers registered for one issuer")

    def verify(self, raw_token: str) -> VerifiedToken:
        if not raw_token or raw_token.count(".") != 2:
            raise unauthenticated()
        try:
            claims = jwt.get_unverified_claims(raw_token)
        except JWTError:
            raise unauthenticated() from None
        issuer = claims.get("iss") if isinstance(claims, dict) else None
        verifier = self._by_issuer.get(issuer) if isinstance(issuer, str) else None
        if verifier is None:
            logger.info("token_rejected", extra={"reason": "unknown_issuer"})
            raise unauthenticated()
        return verifier.verify(raw_token)


def _short_lived(claims: dict[str, Any], max_lifetime: int) -> bool:
    issued, expires = claims.get("iat"), claims.get("exp")
    if not claims.get("jti") or not isinstance(issued, int) or not isinstance(expires, int):
        return False
    return 0 < expires - issued <= max_lifetime


def _actor_chain(act: Any) -> tuple[str, ...]:
    """Unwrap RFC 8693 `act`, which nests: the outermost is the agent acting now.

    Returned in delegation order, innermost first, so the chain reads from the user outwards.
    Anything malformed — not an object, a missing or free-text name, too deep — yields an empty
    tuple, which the caller refuses.
    """
    names: list[str] = []
    current = act
    while current is not None:
        if not isinstance(current, dict) or len(names) >= _MAX_ACTOR_DEPTH:
            return ()
        name = current.get("sub")
        if not isinstance(name, str) or not _ACTOR_NAME.match(name):
            return ()
        names.append(name)
        current = current.get("act")
    return tuple(reversed(names))


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
