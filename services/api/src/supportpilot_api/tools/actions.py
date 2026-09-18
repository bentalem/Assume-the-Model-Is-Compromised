"""Action tools: propose_refund and get_action_status.

`propose_refund` is the tool the whole approval design exists for. Its most important property is
what it does *not* do: it moves no money, calls no provider, and has no path to execution. It
records an intention and stops.

The tool description says so plainly, because the model reads it and should not tell a user their
refund has been issued.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..dependencies import RequestScope, request_scope
from ..errors import business_rule, not_found
from ..pipeline import ResourceContext
from ..repositories.actions import ActionNotApprovable

router = APIRouter(prefix="/v1", tags=["actions"])

ORDER_NUMBER_PATTERN = r"^ORD-[0-9]{4,12}$"
ACTION_ID_PATTERN = r"^[0-9a-fA-F-]{36}$"


class RefundReason(str, Enum):
    damaged_on_arrival = "damaged_on_arrival"
    not_delivered = "not_delivered"
    wrong_item = "wrong_item"
    duplicate_charge = "duplicate_charge"
    other = "other"


class ProposeRefundRequest(BaseModel):
    """The refund proposal body.

    Absent by design: any identity field, any approval field, any destination. The destination is
    derived server-side from the order at execution time — a caller-supplied payout target is how
    refund fraud works.
    """

    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(pattern=ORDER_NUMBER_PATTERN, min_length=8, max_length=16)
    amount: str = Field(
        description="Decimal amount as a string, e.g. '49.90'. Never a float.",
        max_length=16,
    )
    currency: str = Field(
        min_length=3, max_length=3, description="ISO currency code; must match the order"
    )
    reason: RefundReason = Field(
        description=(
            "Why the refund is proposed. One of the listed values exactly — not free text, "
            "and not the customer's wording."
        )
    )
    note: str | None = Field(default=None, max_length=500)

    @field_validator("amount")
    @classmethod
    def amount_is_a_positive_decimal(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise ValueError("amount must be a decimal string") from None
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        if amount.as_tuple().exponent < -2:
            raise ValueError("amount must have at most two decimal places")
        return format(amount, "f")

    @field_validator("currency")
    @classmethod
    def currency_is_uppercase_alpha(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be alphabetic")
        return value.upper()


class ProposeRefundResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    state: str = Field(description="Always PENDING_APPROVAL: no money has moved")
    expires_at: datetime


class ActionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: str
    state: str
    amount: str | None = None
    currency: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    completed_at: datetime | None = None
    provider_reference: str | None = None


@router.post(
    "/actions/refunds",
    operation_id="propose_refund",
    summary="Propose a refund for review. This does not move money.",
    description=(
        "Creates a pending refund request that an independent approver must review. No money moves "
        "when this succeeds. Tell the user their request was submitted for approval — never that "
        "the refund has been issued."
    ),
    response_model=ProposeRefundResponse,
    status_code=201,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        422: {"description": "Rejected by a business limit"},
        503: {"description": "Service unavailable"},
    },
)
def propose_refund(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    payload: ProposeRefundRequest,
) -> ProposeRefundResponse:
    attributes = scope.orders.find_for_subject(
        payload.order_number, scope.subject.organizations if scope.subject else []
    )

    resource = (
        ResourceContext(
            type="order",
            id=attributes.order_number,
            organization_id=attributes.organization_id,
            attributes={
                "status": attributes.status,
                "currency": attributes.currency,
                "total_amount": str(attributes.total_amount),
                # The requested values travel as resource context so policy can compare them
                # against the order without trusting a separate copy from the caller.
                "requested_amount": payload.amount,
                "requested_currency": payload.currency,
            },
        )
        if attributes
        else None
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=scope.subject,
        action="refund.propose",
        resource=resource,
        resource_type="order",
        resource_id=payload.order_number,
    )

    # Policy has already checked the role, the tenant, the order state, the currency, and the
    # limits. These two remain because they are facts about *this* order rather than policy: the
    # amount cannot exceed what was actually paid.
    if attributes is None:
        raise not_found()
    if Decimal(payload.amount) > attributes.total_amount:
        raise business_rule()

    # The frozen payload. This exact object is hashed, and the hash is what an approver approves.
    frozen = {
        "action_type": "refund",
        "order_number": attributes.order_number,
        "organization_id": attributes.organization_id,
        "amount": payload.amount,
        "currency": payload.currency,
        "reason": payload.reason.value,
    }

    try:
        proposed = scope.actions.propose(
            request_id=scope.request_id,
            action_type="refund",
            resource_type="order",
            resource_id=attributes.order_number,
            payload=frozen,
            user_id=auth.subject.user_id,
            organization_id=auth.organization_id,
            roles=auth.subject.roles_in(auth.organization_id),
            policy_version=auth.decision.policy_version,
        )
    except ActionNotApprovable:
        raise business_rule() from None

    return ProposeRefundResponse(
        action_id=proposed.action_id, state=proposed.state, expires_at=proposed.expires_at
    )


@router.get(
    "/actions/{action_id}",
    operation_id="get_action_status",
    summary="Get the status of a previously requested action",
    response_model=ActionStatusResponse,
    response_model_exclude_none=True,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        503: {"description": "Service unavailable"},
    },
)
def get_action_status(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    action_id: Annotated[
        str,
        Path(
            pattern=ACTION_ID_PATTERN,
            description="The action identifier returned by propose_refund",
        ),
    ],
) -> ActionStatusResponse:
    subject = scope.subject
    if subject is None or not subject.organizations:
        raise not_found()

    organization_id = subject.organizations[0]
    resource = ResourceContext(
        type="action_request",
        id=action_id,
        organization_id=organization_id,
        attributes={},
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=subject,
        action="action.read",
        resource=resource,
        resource_type="action_request",
        resource_id=action_id,
    )

    status = scope.actions.status(
        action_id=action_id,
        user_id=auth.subject.user_id,
        organization_id=auth.organization_id,
        roles=auth.subject.roles_in(auth.organization_id),
    )
    if status is None:
        raise not_found()

    scope.pipeline.record_success(request_id=scope.request_id, auth=auth, action="action.read")

    # Never returned: payload_hash, approver identity, job state, lease data, provider response
    # bodies. The requester learns what happened, not how the approval machinery works.
    return ActionStatusResponse(
        action_id=status.action_id,
        action_type=status.action_type,
        state=status.state,
        amount=status.amount,
        currency=status.currency,
        created_at=status.created_at,
        decided_at=status.decided_at,
        completed_at=status.completed_at,
        provider_reference=status.provider_reference,
    )
