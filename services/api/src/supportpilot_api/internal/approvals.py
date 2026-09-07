"""Approval endpoints.

These are **not** tools. They live under /internal, are excluded from the OpenAPI action document,
and are never registered with Onyx. The model has no way to reach them — which is the structural
half of "the model may propose but cannot approve".

The other half is that every check is re-run here at decision time: the approver's authorization is
re-evaluated against current memberships, not against whatever was true when the screen loaded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from ..actions.state import canonical_payload
from ..dependencies import RequestScope, request_scope
from ..errors import business_rule, conflict, forbidden, not_found
from ..pipeline import ResourceContext
from ..repositories.actions import (
    ActionNotApprovable,
    DuplicateDecision,
    SelfApprovalRefused,
)

router = APIRouter(prefix="/internal", tags=["approvals"], include_in_schema=False)

ACTION_ID_PATTERN = r"^[0-9a-fA-F-]{36}$"


class ApprovalView(BaseModel):
    """Everything an approver must see before deciding (SP-BUILD-001 §9)."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: str
    requester_name: str
    organization: str
    resource_id: str
    amount: str
    currency: str
    reason: str
    risk_level: str
    state: str
    expires_at: str
    payload_canonical: str
    payload_hash: str


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(approved|rejected)$")
    #: The hash the approver was shown. A mismatch means the payload changed under them.
    approved_hash: str = Field(pattern="^[0-9a-f]{64}$")
    comment: str | None = Field(default=None, max_length=2000)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    decision: str
    decided_at: str


def _load_and_authorize(scope: RequestScope, action_id: str):
    """Shared by both endpoints: load the action and run the approval policy check."""
    subject = scope.subject
    if subject is None or not subject.organizations:
        raise not_found()

    action = None
    organization_id = None
    for candidate in subject.organizations:
        found = scope.actions.lookup_for_approval(
            action_id, candidate, subject.user_id, subject.roles_in(candidate)
        )
        if found:
            action = found
            organization_id = candidate
            break

    if action is None:
        raise not_found()

    resource = ResourceContext(
        type="action_request",
        id=action_id,
        organization_id=action["organization_id"],
        attributes={
            # requester_id is what the separation-of-duty rule compares against. It comes from the
            # stored row, never from the request.
            "requester_id": action["requester_id"],
            "expires_at": action["expires_at"].isoformat(),
            "state": action["state"],
            "action_type": action["action_type"],
        },
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=subject,
        action="refund.approve",
        resource=resource,
        resource_type="action_request",
        resource_id=action_id,
    )
    return action, auth, organization_id


@router.get("/approvals/{action_id}", response_model=ApprovalView)
def get_approval(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    action_id: Annotated[str, Path(pattern=ACTION_ID_PATTERN)],
) -> ApprovalView:
    action, auth, _ = _load_and_authorize(scope, action_id)

    if action["state"] != "PENDING_APPROVAL":
        # Already decided, cancelled, or executing. Nothing to review.
        raise not_found()

    payload = action["payload"]
    scope.pipeline.record_success(
        request_id=scope.request_id, auth=auth, action="refund.approve.view"
    )

    return ApprovalView(
        action_id=action["id"],
        action_type=action["action_type"],
        requester_name=action["requester_id"],
        organization=action["organization_id"],
        resource_id=action["resource_id"],
        amount=str(payload.get("amount", "")),
        currency=str(payload.get("currency", "")),
        reason=str(payload.get("reason", "")),
        risk_level="high",
        state=action["state"],
        expires_at=action["expires_at"].isoformat(),
        # The canonical form is what was hashed. Showing anything else would mean the approver
        # reviews one thing and authorises another.
        payload_canonical=canonical_payload(payload),
        payload_hash=action["payload_hash"],
    )


@router.post("/approvals/{action_id}", response_model=DecisionResponse, status_code=201)
def post_decision(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    action_id: Annotated[str, Path(pattern=ACTION_ID_PATTERN)],
    payload: DecisionRequest,
) -> DecisionResponse:
    action, auth, organization_id = _load_and_authorize(scope, action_id)

    # The screen the approver saw must still describe the action. If the stored hash has moved on,
    # the approver is looking at something that no longer exists.
    if payload.approved_hash != action["payload_hash"]:
        raise business_rule()

    if action["state"] != "PENDING_APPROVAL":
        raise conflict()

    try:
        decided_at = scope.actions.decide(
            request_id=scope.request_id,
            action_id=action_id,
            decision=payload.decision,
            approved_hash=action["payload_hash"],
            comment=payload.comment,
            approver_id=auth.subject.user_id,
            organization_id=action["organization_id"],
            roles=auth.subject.roles_in(action["organization_id"]),
            policy_version=auth.decision.policy_version or "unknown",
        )
    except SelfApprovalRefused:
        # The database trigger caught it. Policy should have refused first, so reaching here means
        # the two disagree — worth surfacing as forbidden rather than a generic error.
        raise forbidden() from None
    except DuplicateDecision:
        raise conflict() from None
    except ActionNotApprovable:
        raise conflict() from None

    return DecisionResponse(
        action_id=action_id,
        decision=payload.decision,
        decided_at=decided_at.isoformat(),
    )
