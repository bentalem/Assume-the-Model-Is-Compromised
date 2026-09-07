"""TS-5 / TS1-12 — the pipeline's own guarantees.

Covered here:
  * field minimization is a whitelist, applied to the record before it is serialized;
  * a denial is audited before the error is raised;
  * cross-tenant and unknown resources produce the identical 404 answer;
  * a policy outage is a 503, not a 404;
  * the policy input is built from the loaded subject and resource, never from caller input.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from supportpilot_api.audit.writer import AuditEvent
from supportpilot_api.auth.tokens import VerifiedToken
from supportpilot_api.pipeline import Authorization, Pipeline, ResourceContext
from supportpilot_api.policy.client import Decision
from supportpilot_api.repositories.memberships import Subject

from .conftest import ALICE_SUB, ALICE_UUID, CEDAR, NORTHWIND


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class StubPolicy:
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        self.last_input: dict | None = None

    def decide(self, *, subject, action, resource, context):
        self.last_input = {
            "subject": subject,
            "action": action,
            "resource": resource,
            "context": context,
        }
        return self.decision


ALLOW = Decision(
    allow=True,
    reason="same_organization_and_allowed_role",
    policy_version="2026-09-07.1",
    obligations={"allowed_fields": ["order_number", "status"]},
)
DENY = Decision(
    allow=False, reason="not_a_member_of_resource_organization", policy_version="2026-09-07.1"
)
OUTAGE = Decision(
    allow=False, reason="policy_unavailable", policy_version=None, unavailable=True
)


@pytest.fixture
def token() -> VerifiedToken:
    return VerifiedToken(
        subject=ALICE_SUB,
        token_id="t1",
        issued_at=0,
        expires_at=0,
        authentication_level="mfa",
        scopes=frozenset(),
    )


@pytest.fixture
def alice() -> Subject:
    return Subject(
        user_id=ALICE_UUID,
        identity_subject=ALICE_SUB,
        display_name="Alice Nguyen",
        memberships={CEDAR: ["support_agent"]},
        authentication_level="mfa",
    )


def cedar_order() -> ResourceContext:
    return ResourceContext(
        type="order",
        id="ORD-2001",
        organization_id=CEDAR,
        attributes={"status": "shipped", "currency": "USD", "total_amount": "149.90"},
    )


def build(decision: Decision) -> tuple[Pipeline, StubPolicy, RecordingAudit]:
    policy = StubPolicy(decision)
    audit = RecordingAudit()
    return Pipeline(policy, audit), policy, audit


def authorize(pipeline, token, subject, resource):
    return pipeline.authorize(
        request_id="req-1",
        token=token,
        subject=subject,
        action="order.read",
        resource=resource,
        resource_type="order",
        resource_id="ORD-2001",
    )


# Allow path ------------------------------------------------------------------------------------
def test_allow_returns_authorization(token, alice):
    pipeline, _, _ = build(ALLOW)
    auth = authorize(pipeline, token, alice, cedar_order())
    assert auth.organization_id == CEDAR
    assert auth.decision.allow is True


def test_policy_input_uses_loaded_subject_and_resource(token, alice):
    pipeline, policy, _ = build(ALLOW)
    authorize(pipeline, token, alice, cedar_order())

    sent = policy.last_input
    assert sent["subject"]["id"] == ALICE_UUID  # database uuid, not the token 'sub'
    assert sent["subject"]["roles"] == ["support_agent"]  # from memberships
    assert sent["resource"]["organization_id"] == CEDAR  # from the database row
    assert sent["action"] == "order.read"


def test_roles_are_scoped_to_the_resource_tenant(token):
    """A user in two tenants sends only the roles held in the tenant being accessed."""
    multi = Subject(
        user_id=ALICE_UUID,
        identity_subject=ALICE_SUB,
        display_name="Alice",
        memberships={CEDAR: ["support_agent"], NORTHWIND: ["support_manager"]},
        authentication_level="mfa",
    )
    pipeline, policy, _ = build(ALLOW)
    authorize(pipeline, token, multi, cedar_order())
    assert policy.last_input["subject"]["roles"] == ["support_agent"]


# Minimization ----------------------------------------------------------------------------------
def test_minimize_is_a_whitelist(token, alice):
    pipeline, _, _ = build(ALLOW)
    auth = authorize(pipeline, token, alice, cedar_order())

    record = {
        "order_number": "ORD-2001",
        "status": "shipped",
        "currency": "USD",
        "total_amount": "149.90",
        "customer_id": "leak",
        "organization_id": CEDAR,
    }
    assert auth.minimize(record) == {"order_number": "ORD-2001", "status": "shipped"}


def test_minimize_without_obligations_returns_record(token, alice):
    pipeline, _, _ = build(
        Decision(allow=True, reason="ok", policy_version="1", obligations={})
    )
    auth = authorize(pipeline, token, alice, cedar_order())
    assert auth.minimize({"a": 1}) == {"a": 1}


# Deny paths ------------------------------------------------------------------------------------
def test_policy_deny_is_404_and_audited(token, alice):
    pipeline, _, audit = build(DENY)
    with pytest.raises(HTTPException) as exc:
        authorize(pipeline, token, alice, cedar_order())

    assert exc.value.status_code == 404
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.decision == "denied"
    assert event.reason == "not_a_member_of_resource_organization"
    assert event.policy_version == "2026-09-07.1"
    assert event.actor_id == ALICE_UUID


def test_invisible_resource_is_404_and_audited(token, alice):
    """A cross-tenant order never resolves, so the resource is None. Same answer as unknown."""
    pipeline, policy, audit = build(ALLOW)
    with pytest.raises(HTTPException) as exc:
        authorize(pipeline, token, alice, None)

    assert exc.value.status_code == 404
    assert audit.events[0].reason == "resource_not_visible"
    # Policy was never consulted: there was no trusted resource to ask about.
    assert policy.last_input is None


def test_cross_tenant_and_unknown_are_indistinguishable(token, alice):
    pipeline, _, _ = build(ALLOW)
    codes = []
    for resource in (None, None):
        with pytest.raises(HTTPException) as exc:
            authorize(pipeline, token, alice, resource)
        codes.append((exc.value.status_code, exc.value.detail))
    assert codes[0] == codes[1] == (404, "not_found")


def test_policy_outage_is_503_not_404(token, alice):
    """An outage must not be reported as a missing resource — that would hide the failure."""
    pipeline, _, audit = build(OUTAGE)
    with pytest.raises(HTTPException) as exc:
        authorize(pipeline, token, alice, cedar_order())

    assert exc.value.status_code == 503
    assert audit.events[0].reason == "policy_unavailable"


def test_unknown_subject_is_404_and_audited(token):
    """Verified token, but no active application user."""
    pipeline, policy, audit = build(ALLOW)
    with pytest.raises(HTTPException) as exc:
        authorize(pipeline, token, None, cedar_order())

    assert exc.value.status_code == 404
    assert audit.events[0].reason == "unknown_subject"
    assert audit.events[0].actor_id == ALICE_SUB  # falls back to the token subject
    assert policy.last_input is None


# Audit resilience ------------------------------------------------------------------------------
def test_audit_failure_does_not_turn_a_denial_into_success(token, alice):
    class BrokenAudit:
        def record(self, event):
            raise RuntimeError("audit database down")

    pipeline = Pipeline(StubPolicy(DENY), BrokenAudit())
    with pytest.raises(HTTPException) as exc:
        authorize(pipeline, token, alice, cedar_order())
    assert exc.value.status_code == 404


def test_success_is_audited_with_policy_version(token, alice):
    pipeline, _, audit = build(ALLOW)
    auth = authorize(pipeline, token, alice, cedar_order())
    pipeline.record_success(request_id="req-1", auth=auth, action="order.read")

    event = audit.events[-1]
    assert event.decision == "allowed"
    assert event.action == "order.read"
    assert event.organization_id == CEDAR
    assert event.policy_version == "2026-09-07.1"
