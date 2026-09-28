"""RFC 8693 token exchange: who may obtain what, for whom.

    effective permission  =  what the user may do  ∩  the agent's ceiling  ∩  what this task needs

The broker owns the middle term and bounds the third. The first stays where it always was: the
API loads the user's roles from the database on every request, and nothing minted here changes that.

The rules, and the lab switch that loosens each one (every switch a configuration a real deployment
might ship, never a code path written to be wrong):

    subject is a user's token     requested ⊆ the profile's ceiling
        ceiling.user_only         requested ⊆ every delegable scope — "agent-requested scopes,
                                  auto-approved". Only the API's role check is left (1.7)

    subject is a delegated token  requested ⊆ the subject token's own scope; `act` nests;
                                  lifetime ≤ what the subject token has left
        chain.widen               requested ⊆ the new profile's ceiling instead — the chain can
                                  widen (1.8)

Never delegable, whatever the switches say: a scope in `never_delegable`. The policy refuses it at
the resource server too.

Errors are RFC 6749 / 8693 codes, and the body never echoes a token or a value that was sent.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from .tokens import MAX_ACTOR_DEPTH, MAX_LIFETIME_SECONDS, Minter, TokenRefused, UserVerifier
from .tokens import unverified_issuer
from .trusted import Profile, ScopeTable

logger = logging.getLogger("supportpilot.broker.exchange")

GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE_ACCESS = "urn:ietf:params:oauth:token-type:access_token"
SUBJECT_TOKEN_TYPES = frozenset({TOKEN_TYPE_ACCESS, "urn:ietf:params:oauth:token-type:jwt"})
_MAX_SCOPES = 16


@dataclass(frozen=True)
class Outcome:
    status: int
    body: dict[str, Any]
    #: The minted claims, for the log and for nothing else. Never the token.
    claims: dict[str, Any] | None = None


def _error(status: int, code: str, reason: str) -> Outcome:
    logger.info("exchange_refused", extra={"error": code, "reason": reason})
    return Outcome(status, {"error": code, "error_description": reason})


def exchange(
    form: dict[str, str],
    *,
    client: Profile | None,
    scopes: ScopeTable,
    settings: dict[str, bool],
    users: UserVerifier,
    minter: Minter,
    now: int | None = None,
) -> Outcome:
    now = int(now if now is not None else time.time())

    if form.get("grant_type") != GRANT_TYPE:
        return _error(400, "unsupported_grant_type", "grant_type_not_token_exchange")
    if client is None:
        return _error(401, "invalid_client", "client_authentication_failed")

    subject_token = form.get("subject_token", "")
    if not subject_token or form.get("subject_token_type") not in SUBJECT_TOKEN_TYPES:
        return _error(400, "invalid_request", "subject_token_missing_or_untyped")
    if form.get("requested_token_type", TOKEN_TYPE_ACCESS) != TOKEN_TYPE_ACCESS:
        return _error(400, "invalid_request", "requested_token_type_unsupported")
    if form.get("audience", minter.audience) != minter.audience:
        return _error(400, "invalid_target", "audience_not_served")

    requested = frozenset(form.get("scope", "").split())
    if not requested or len(requested) > _MAX_SCOPES:
        return _error(400, "invalid_scope", "scope_missing")
    if not requested <= scopes.known:
        return _error(400, "invalid_scope", "scope_unknown")
    if requested & scopes.never_delegable:
        return _error(400, "invalid_scope", "scope_never_delegable")

    issuer = unverified_issuer(subject_token)
    try:
        if issuer == users.issuer:
            user = users.verify(subject_token)
            allowed = scopes.delegable if settings["ceiling.user_only"] else client.ceiling
            if not requested <= allowed:
                return _error(400, "invalid_scope", "scope_exceeds_profile")
            subject, act, not_after, acr = user.subject, {"sub": client.name}, user.expires_at, user.acr
            rule = "user_only" if settings["ceiling.user_only"] else "profile_ceiling"

        elif issuer == minter.issuer:
            delegated = minter.verify_own(subject_token)
            if delegated.depth >= MAX_ACTOR_DEPTH:
                return _error(400, "invalid_request", "delegation_chain_too_long")
            allowed = client.ceiling if settings["chain.widen"] else delegated.scopes
            if not requested <= allowed:
                return _error(400, "invalid_scope", "scope_exceeds_subject_token")
            subject, not_after, acr = delegated.subject, delegated.expires_at, delegated.acr
            act = {"sub": client.name, "act": delegated.act}
            rule = "chain_widen" if settings["chain.widen"] else "narrow_only"

        else:
            return _error(400, "invalid_request", "subject_token_issuer_unknown")

        token, claims = minter.mint(
            subject=subject, act=act, scopes=requested, lifetime_seconds=MAX_LIFETIME_SECONDS,
            not_after=not_after, acr=acr, now=now,
        )
    except TokenRefused as refused:
        return _error(400, "invalid_request", refused.reason)

    logger.info(
        "exchange_minted",
        extra={"profile": client.name, "rule": rule, "scope": claims["scope"],
               "depth": _depth(act), "expires_in": claims["exp"] - claims["iat"]},
    )
    return Outcome(
        200,
        {
            "access_token": token,
            "issued_token_type": TOKEN_TYPE_ACCESS,
            "token_type": "Bearer",
            "expires_in": claims["exp"] - claims["iat"],
            "scope": claims["scope"],
        },
        claims,
    )


def _depth(act: dict[str, Any]) -> int:
    depth, current = 0, act
    while isinstance(current, dict):
        depth += 1
        current = current.get("act")
    return depth
