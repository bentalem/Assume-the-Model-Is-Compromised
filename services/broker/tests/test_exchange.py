"""RFC 8693 exchange: the ceiling, narrowing on re-exchange, nesting, and the two switches."""

from __future__ import annotations

import time

import pytest

from delegation_broker.exchange import TOKEN_TYPE_ACCESS, GRANT_TYPE, exchange
from delegation_broker.tokens import Minter, SigningKey

from .conftest import ALICE_SUB, AUDIENCE, BROKER, claims_of

SECURE = {"broker.passthrough": False, "ceiling.user_only": False, "chain.widen": False}


def form(subject_token: str, scope: str, **extra: str) -> dict[str, str]:
    return {"grant_type": GRANT_TYPE, "subject_token": subject_token,
            "subject_token_type": TOKEN_TYPE_ACCESS, "scope": scope, **extra}


@pytest.fixture
def run(scopes, users, minter, profiles):
    def _run(data, *, as_profile="status-helper", settings=None, now=None):
        client = profiles.get(as_profile) if as_profile else None
        return exchange(data, client=client, scopes=scopes, settings=settings or SECURE,
                        users=users, minter=minter, now=now)
    return _run


# --- a user's token, exchanged by an agent -------------------------------------------------------------
def test_an_agent_obtains_a_narrow_token_that_names_the_user_and_itself(run, user_token):
    outcome = run(form(user_token(), "orders:read"))
    assert outcome.status == 200
    claims = claims_of(outcome.body["access_token"])
    assert claims["sub"] == ALICE_SUB
    assert claims["act"] == {"sub": "status-helper"}
    assert claims["aud"] == AUDIENCE and claims["iss"] == BROKER
    assert claims["scope"] == "orders:read"
    assert claims["exp"] - claims["iat"] <= 300
    assert claims["jti"]
    assert outcome.body["issued_token_type"] == TOKEN_TYPE_ACCESS


def test_an_agent_cannot_obtain_more_than_its_ceiling(run, user_token):
    outcome = run(form(user_token(), "customers:read"))
    assert (outcome.status, outcome.body["error"]) == (400, "invalid_scope")
    assert outcome.body["error_description"] == "scope_exceeds_profile"
    assert "access_token" not in outcome.body


def test_asking_for_less_than_the_ceiling_is_fine(run, user_token):
    outcome = run(form(user_token(), "orders:read"), as_profile="refund-assistant")
    assert claims_of(outcome.body["access_token"])["scope"] == "orders:read"


def test_armed_user_only_grants_what_the_user_has_rather_than_what_the_agent_may(run, user_token):
    # 1.7: agent-requested scopes, auto-approved. The API's role check is all that is left.
    outcome = run(form(user_token(), "customers:read"),
                  settings={**SECURE, "ceiling.user_only": True})
    assert outcome.status == 200
    assert claims_of(outcome.body["access_token"])["scope"] == "customers:read"


@pytest.mark.parametrize("settings", [SECURE, {**SECURE, "ceiling.user_only": True},
                                      {**SECURE, "chain.widen": True}])
def test_approval_is_never_minted_whatever_is_armed(run, user_token, settings):
    outcome = run(form(user_token(), "refunds:approve"), as_profile="refund-assistant",
                  settings=settings)
    assert outcome.body.get("error_description") == "scope_never_delegable"


def test_a_token_never_outlives_the_users(run, user_token):
    now = int(time.time())
    outcome = run(form(user_token(exp=now + 40), "orders:read"), now=now)
    claims = claims_of(outcome.body["access_token"])
    assert claims["exp"] <= now + 40


# --- a delegated token, exchanged again ---------------------------------------------------------------
def test_re_exchange_narrows_and_nests_act(run, user_token):
    first = run(form(user_token(), "orders:read refunds:propose"), as_profile="refund-assistant")
    second = run(form(first.body["access_token"], "orders:read"), as_profile="status-helper")
    assert second.status == 200
    claims = claims_of(second.body["access_token"])
    assert claims["scope"] == "orders:read"
    assert claims["act"] == {"sub": "status-helper", "act": {"sub": "refund-assistant"}}
    assert claims["sub"] == ALICE_SUB
    assert claims["exp"] <= claims_of(first.body["access_token"])["exp"]


def test_re_exchange_cannot_widen_past_the_subject_token(run, user_token):
    # 1.8: a sub-agent holding an orders:read token asks for customers:read.
    first = run(form(user_token(), "orders:read"), as_profile="status-helper")
    second = run(form(first.body["access_token"], "refunds:propose"), as_profile="refund-assistant")
    assert second.body["error_description"] == "scope_exceeds_subject_token"


def test_armed_chain_widen_lets_the_chain_grow(run, user_token):
    first = run(form(user_token(), "orders:read"), as_profile="status-helper")
    second = run(form(first.body["access_token"], "refunds:propose"), as_profile="refund-assistant",
                 settings={**SECURE, "chain.widen": True})
    assert second.status == 200
    claims = claims_of(second.body["access_token"])
    assert claims["scope"] == "refunds:propose"
    assert claims["act"] == {"sub": "refund-assistant", "act": {"sub": "status-helper"}}


def test_a_chain_is_bounded_in_depth(run, user_token):
    token = run(form(user_token(), "orders:read")).body["access_token"]
    for _ in range(3):
        token = run(form(token, "orders:read")).body["access_token"]
    outcome = run(form(token, "orders:read"))
    assert outcome.body["error_description"] == "delegation_chain_too_long"


def test_a_delegated_token_signed_by_another_key_is_not_exchanged(run, other_signing_pem):
    forger = Minter(SigningKey(other_signing_pem), issuer=BROKER, audience=AUDIENCE)
    forged, _ = forger.mint(subject=ALICE_SUB, act={"sub": "status-helper"},
                            scopes=frozenset({"orders:read", "customers:read"}), lifetime_seconds=300)
    outcome = run(form(forged, "customers:read"))
    assert outcome.body["error_description"] == "subject_token_invalid"


# --- the request itself ---------------------------------------------------------------------------------
def test_an_unauthenticated_client_gets_nothing(run, user_token):
    outcome = run(form(user_token(), "orders:read"), as_profile=None)
    assert (outcome.status, outcome.body["error"]) == (401, "invalid_client")


def test_the_wrong_grant_type_is_refused(run, user_token):
    outcome = run({**form(user_token(), "orders:read"), "grant_type": "password"})
    assert outcome.body["error"] == "unsupported_grant_type"


@pytest.mark.parametrize("scope", ["", "orders:*", "orders:read admin", " ".join(f"s{i}" for i in range(20))])
def test_a_missing_or_unknown_scope_is_refused(run, user_token, scope):
    assert run(form(user_token(), scope)).body["error"] == "invalid_scope"


def test_another_audience_is_refused(run, user_token):
    outcome = run(form(user_token(), "orders:read", audience="supportpilot-memory"))
    assert outcome.body["error"] == "invalid_target"


def test_a_user_token_carrying_act_is_not_a_user_token(run, user_token):
    outcome = run(form(user_token(act={"sub": "refund-assistant"}), "orders:read"))
    assert outcome.body["error_description"] == "user_token_invalid"


def test_an_expired_user_token_is_refused(run, user_token):
    now = int(time.time())
    outcome = run(form(user_token(iat=now - 900, exp=now - 600), "orders:read"))
    assert outcome.body["error_description"] == "user_token_invalid"


def test_an_unknown_issuer_is_refused(run, user_token):
    outcome = run(form(user_token(iss="https://elsewhere/realms/x"), "orders:read"))
    assert outcome.body["error_description"] == "subject_token_issuer_unknown"


def test_no_error_echoes_the_token(run, user_token):
    token = user_token(act={"sub": "x"})
    outcome = run(form(token, "orders:read"))
    assert token not in str(outcome.body)
