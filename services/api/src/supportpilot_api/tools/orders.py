"""The get_order tool.

The only operation registered with Onyx in phase 1. Its schema is the contract the model sees, so
it is deliberately narrow: one path parameter with a strict pattern, and a response model that
cannot carry a field the policy did not allow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import RequestScope, request_scope
from ..pipeline import ResourceContext

router = APIRouter(prefix="/v1", tags=["orders"])

ORDER_NUMBER_PATTERN = r"^ORD-[0-9]{4,12}$"


class OrderResponse(BaseModel):
    """The bounded response schema.

    `extra="forbid"` means a field the repository adds later cannot reach the caller until someone
    adds it here deliberately — response minimization by construction rather than by review.
    """

    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(description="The order identifier, e.g. ORD-2001")
    status: str = Field(description="Order lifecycle status")
    currency: str = Field(min_length=3, max_length=3)
    total_amount: str = Field(description="Decimal amount as a string, to avoid float rounding")
    placed_at: datetime
    updated_at: datetime


@router.get(
    "/orders/{order_number}",
    operation_id="get_order",
    summary="Get an order visible to the authenticated user",
    response_model=OrderResponse,
    response_model_exclude_none=True,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        503: {"description": "Service unavailable"},
    },
)
def get_order(
    request: Request,
    order_number: Annotated[
        str,
        Path(
            pattern=ORDER_NUMBER_PATTERN,
            min_length=8,
            max_length=16,
            description="Order number in the form ORD-nnnn",
            examples=["ORD-2001"],
        ),
    ],
    scope: Annotated[RequestScope, Depends(request_scope)],
) -> OrderResponse:
    # Step 1 (schema) and 2 (token) are already done: the path pattern rejected a malformed
    # identifier before this body ran, and `request_scope` verified the token and loaded the
    # subject before any resource was touched.

    # Step 4 — trusted resource attributes, scoped to the caller's own tenants.
    attributes = scope.orders.find_for_subject(
        order_number, scope.subject.organizations if scope.subject else []
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
            },
        )
        if attributes
        else None
    )

    # Steps 5 and 6 — policy input built from verified identity and the loaded resource, then OPA.
    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=scope.subject,
        action="order.read",
        resource=resource,
        resource_type="order",
        resource_id=order_number,
    )

    # Steps 7 and 8 — the authorized read, under transaction-local request context. Row security
    # filters this a second time even though policy already allowed it.
    record = scope.orders.read_authorized(
        order_number=order_number,
        user_id=auth.subject.user_id,
        organization_id=auth.organization_id,
    )
    if record is None:
        # Allowed by policy but invisible to row security: the two layers disagree, which means a
        # policy or context bug. Refuse, and make the disagreement loud in the audit trail.
        scope.pipeline.record_success(
            request_id=scope.request_id,
            auth=auth,
            action="order.read.rls_empty",
        )
        from ..errors import not_found

        raise not_found()

    # Step 9 — field obligations, then step 10, the audit event.
    minimized = auth.minimize(record.as_dict())
    scope.pipeline.record_success(request_id=scope.request_id, auth=auth, action="order.read")

    # Step 12 — the bounded response.
    return OrderResponse(**minimized)
