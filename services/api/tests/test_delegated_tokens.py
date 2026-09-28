"""Track 1, 1.5 - 1.8 — a second issuer, and what the API does with a delegated token.

Covered here:
  * a Keycloak token behaves exactly as before, and may not carry `act`;
  * a broker token must carry `act`, ES256 only, five minutes at most, with a `jti`;
  * a token is verified only against the issuer it names — issuer confusion in both directions;
  * the actor chain is read from nested `act` in delegation order, and anything malformed is refused;
  * the pipeline tells the policy about a delegated token and only about a delegated one;
  * the audit trail names the human as the actor and the agent beside them.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jose import jwk, jwt

from supportpilot_api.audit.writer import AuditEvent
from supportpilot_api.auth.tokens import (
    ACTOR_REQUIRED,
    IssuerRegistry,
    TokenVerifier,
    VerifiedToken,
)
from supportpilot_api.pipeline import Pipeline, ResourceContext
from supportpilot_api.policy.client import Decision
from supportpilot_api.repositories.memberships import Subject

from .conftest import ALICE_SUB, ALICE_UUID, AUDIENCE, CEDAR, ISSUER, NORTHWIND, StubJwks

BROKER = "http://broker:8097"


@pytest.fixture(scope="module")
def broker_key() -> dict[str, Any]:
    """An ES256 key pair, in the JWK shape the broker publishes."""
    private = ec.generate_private_key(ec.SECP256R1())
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem, algorithm="ES256").to_dict()
    public_jwk["kid"] = "broker-key-1"
    public_jwk["alg"] = "ES256"
    return {"private_pem": private_pem, "public_jwk": public_jwk, "kid": "broker-key-1"}


@pytest.fixture
def registry(signing_key, broker_key) -> IssuerRegistry:
    return IssuerRegistry(
        [
            TokenVerifier(
                issuer=ISSUER, audience=AUDIENCE, jwks=StubJwks(signing_key["public_jwk"]),
                leeway_seconds=5,
            ),
            TokenVerifier(
                issuer=BROKER, audience=AUDIENCE, jwks=StubJwks(broker_key["public_jwk"]),
                leeway_seconds=5, allowed_algorithms=frozenset({"ES256"}),
                actor=ACTOR_REQUIRED, max_lifetime_seconds=300,
            ),
        ]
    )


@pytest.fixture
def mint(broker_key):
    """A broker-shaped token, any claim overridable, signed with the broker's key by default."""

    def _mint(*, key: str | None = None, kid: str | None = None, alg: str = "ES256",
              drop: tuple[str, ...] = (), **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": BROKER,
            "sub": ALICE_SUB,
            "aud": AUDIENCE,
            "act": {"sub": "status-helper"},
            "scope": "orders:read",
            "iat": now,
            "exp": now + 300,
            "jti": "delegated-1",
        }
        claims.update(overrides)
        for name in drop:
            claims.pop(name, None)
        return jwt.encode(
            claims, key or broker_key["private_pem"], algorithm=alg,
            headers={"kid": kid or broker_key["kid"]},
        )

    return _mint


def refused(registry: IssuerRegistry, token: str) -> None:
    with pytest.raises(HTTPException) as exc:
        registry.verify(token)
    assert exc.value.status_code == 401


# --- the Keycloak path is unchanged, except that it may not carry an actor ----------------------
def test_a_users_own_token_is_accepted_and_names_no_agent(registry, make_token):
    token = registry.verify(make_token())
    assert token.subject == ALICE_SUB
    assert token.actor_chain == ()
    assert token.is_delegated is False
    assert token.agent_id is None


def test_a_keycloak_token_carrying_act_is_refused(registry, make_token):
    refused(registry, make_token(act={"sub": "status-helper"}))


# --- a broker token -------------------------------------------------------------------------------
def test_a_delegated_token_names_the_user_the_agent_and_the_scope(registry, mint):
    token = registry.verify(mint(scope="orders:read actions:read"))
    assert token.subject == ALICE_SUB
    assert token.actor_chain == ("status-helper",)
    assert token.agent_id == "status-helper"
    assert token.scopes == frozenset({"orders:read", "actions:read"})


def test_nested_act_is_read_in_delegation_order(registry, mint):
    # RFC 8693: the outermost act is the agent acting now; the one inside it acted before.
    token = registry.verify(
        mint(act={"sub": "refund-assistant", "act": {"sub": "status-helper"}})
    )
    assert token.actor_chain == ("status-helper", "refund-assistant")
    assert token.agent_id == "status-helper > refund-assistant"


def test_a_broker_token_without_act_is_refused(registry, mint):
    refused(registry, mint(drop=("act",)))


@pytest.mark.parametrize(
    "act",
    [
        "status-helper",                      # a string, not an object
        {},                                   # no name
        {"sub": ""},
        {"sub": "Ignore previous instructions"},  # free text, not a profile name
        {"sub": "status-helper", "act": "x"},     # a malformed inner hop
        {"sub": "a", "act": {"sub": "b", "act": {"sub": "c", "act": {"sub": "d", "act": {"sub": "e"}}}}},
    ],
)
def test_a_malformed_actor_is_refused_not_ignored(registry, mint, act):
    refused(registry, mint(act=act))


def test_a_broker_token_for_another_audience_is_refused(registry, mint):
    refused(registry, mint(aud="supportpilot-broker"))


def test_a_broker_token_living_longer_than_five_minutes_is_refused(registry, mint):
    now = int(time.time())
    refused(registry, mint(iat=now, exp=now + 301))


def test_a_broker_token_without_a_jti_is_refused(registry, mint):
    refused(registry, mint(drop=("jti",)))


# --- issuer confusion ------------------------------------------------------------------------------
def test_the_brokers_key_cannot_sign_a_keycloak_token(registry, mint):
    # Names Keycloak, signed by the broker: Keycloak's key set has no such key.
    refused(registry, mint(iss=ISSUER, drop=("act",)))


def test_keycloaks_key_cannot_sign_a_broker_token(registry, signing_key, mint):
    # Names the broker, signed with Keycloak's RSA key: RS256 is not an algorithm the broker uses.
    refused(registry, mint(key=signing_key["private_pem"], kid=signing_key["kid"], alg="RS256"))


def test_a_broker_token_signed_with_a_keycloak_key_id_is_refused(registry, signing_key, mint):
    refused(registry, mint(kid=signing_key["kid"]))


def test_an_unknown_issuer_is_refused(registry, mint):
    refused(registry, mint(iss="http://broker.evil:8097"))


@pytest.mark.parametrize("raw", ["", "not-a-token", "a.b", "a.b.c", "....."])
def test_malformed_tokens_are_refused_by_the_registry(registry, raw):
    refused(registry, raw)


def test_an_issuer_may_not_widen_the_algorithm_allowlist(broker_key):
    with pytest.raises(ValueError):
        TokenVerifier(
            issuer=BROKER, audience=AUDIENCE, jwks=StubJwks(broker_key["public_jwk"]),
            allowed_algorithms=frozenset({"ES256", "HS256"}),
        )


def test_two_verifiers_for_one_issuer_are_refused(signing_key):
    one = TokenVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=StubJwks(signing_key["public_jwk"]))
    with pytest.raises(ValueError):
        IssuerRegistry([one, one])


# --- the pipeline -----------------------------------------------------------------------------------
class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class RecordingPolicy:
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        self.calls: list[dict] = []

    def decide(self, **kwargs):
        self.calls.append(kwargs)
        return self.decision


ALLOW = Decision(allow=True, reason="same_organization_and_allowed_role",
                 policy_version="2026-09-28.1", obligations={})
DENY = Decision(allow=False, reason="scope_not_granted", policy_version="2026-09-28.1")


def verified(chain: tuple[str, ...] = (), scopes: frozenset[str] = frozenset()) -> VerifiedToken:
    return VerifiedToken(subject=ALICE_SUB, token_id="t", issued_at=0, expires_at=0,
                         authentication_level="mfa", scopes=scopes, actor_chain=chain)


ALICE = Subject(user_id=ALICE_UUID, identity_subject=ALICE_SUB, display_name="Alice Nguyen",
                memberships={CEDAR: ["support_agent"]}, authentication_level="mfa")

ORDER = ResourceContext(type="order", id="ORD-2001", organization_id=CEDAR, attributes={})


def authorize(pipeline: Pipeline, token: VerifiedToken, resource=ORDER, action="order.read"):
    return pipeline.authorize(request_id="req-1", token=token, subject=ALICE, action=action,
                              resource=resource, resource_type="order", resource_id="ORD-2001")


def test_a_users_own_token_sends_the_policy_no_delegation():
    policy, audit = RecordingPolicy(ALLOW), RecordingAudit()
    authorize(Pipeline(policy, audit), verified())
    assert "delegation" not in policy.calls[0]


def test_a_delegated_token_sends_the_chain_and_scope_to_the_policy():
    policy, audit = RecordingPolicy(ALLOW), RecordingAudit()
    auth = authorize(Pipeline(policy, audit), verified(("status-helper",), frozenset({"orders:read"})))
    assert policy.calls[0]["delegation"] == {
        "actor": "status-helper", "chain": ["status-helper"], "scopes": ["orders:read"],
    }
    # The subject is still the one loaded from the database, never anything from the token.
    assert policy.calls[0]["subject"]["id"] == ALICE_UUID
    assert policy.calls[0]["subject"]["roles"] == ["support_agent"]
    assert auth.agent_id == "status-helper"


def test_a_delegated_denial_is_audited_with_the_human_as_actor_and_the_agent_beside():
    policy, audit = RecordingPolicy(DENY), RecordingAudit()
    with pytest.raises(HTTPException) as exc:
        authorize(Pipeline(policy, audit), verified(("status-helper",), frozenset({"orders:read"})))
    assert exc.value.status_code == 404
    event = audit.events[0]
    assert (event.actor_type, event.actor_id, event.agent_id) == ("user", ALICE_UUID, "status-helper")
    assert (event.decision, event.reason) == ("denied", "scope_not_granted")


def test_a_delegated_success_is_audited_with_the_agent():
    policy, audit = RecordingPolicy(ALLOW), RecordingAudit()
    pipeline = Pipeline(policy, audit)
    auth = authorize(pipeline, verified(("status-helper", "refund-assistant"), frozenset({"orders:read"})))
    pipeline.record_success(request_id="req-1", auth=auth, action="order.read")
    assert audit.events[0].agent_id == "status-helper > refund-assistant"
    assert audit.events[0].actor_id == ALICE_UUID


def test_a_delegated_cross_tenant_read_is_refused_before_the_policy_and_still_names_the_agent():
    policy, audit = RecordingPolicy(ALLOW), RecordingAudit()
    with pytest.raises(HTTPException) as exc:
        Pipeline(policy, audit).authorize(
            request_id="req-1", token=verified(("status-helper",), frozenset({"orders:read"})),
            subject=ALICE, action="order.read", resource=None,
            resource_type="order", resource_id="ORD-3001",
        )
    assert exc.value.status_code == 404
    assert policy.calls == []
    assert audit.events[0].reason == "resource_not_visible"
    assert audit.events[0].agent_id == "status-helper"
    assert NORTHWIND not in ALICE.organizations


def test_the_audit_writer_sends_agent_id():
    event = AuditEvent(request_id="r", actor_id=ALICE_UUID, action="order.read",
                       decision="allowed", reason="x", agent_id="status-helper")
    assert event.as_params()["agent_id"] == "status-helper"
    assert AuditEvent(request_id="r", actor_id="u", action="a", decision="allowed",
                      reason="x").as_params()["agent_id"] is None
