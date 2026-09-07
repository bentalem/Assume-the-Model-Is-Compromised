"""Customer tools: search_customers and get_customer."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import RequestScope, request_scope
from ..errors import not_found
from ..pipeline import ResourceContext
from ..repositories.pagination import MAX_LIMIT, clamp_limit

router = APIRouter(prefix="/v1", tags=["customers"])

CUSTOMER_REF_PATTERN = r"^CUS-[0-9]{4,12}$"


class CustomerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_ref: str
    full_name: str
    assigned_team: str | None = None


class CustomerSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # maxItems is not decoration: it is the schema-level statement that this endpoint cannot be
    # used for bulk extraction, and the export audit rejects an unbounded array.
    results: list[CustomerSummary] = Field(max_length=MAX_LIMIT)
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page, or null when there are no more"
    )


class CustomerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_ref: str
    full_name: str
    # Absent for a restricted customer unless the caller is a manager or auditor. The policy
    # obligation removes it before this model is constructed.
    email: str | None = None
    assigned_team: str | None = None
    open_ticket_count: int | None = None


@router.get(
    "/customers",
    operation_id="search_customers",
    summary="Find customers visible to the authenticated user",
    response_model=CustomerSearchResponse,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        503: {"description": "Service unavailable"},
    },
)
def search_customers(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            max_length=80,
            description="Part of a customer name to search for",
            examples=["Priya"],
        ),
    ],
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CustomerSearchResponse:
    subject = scope.subject
    if subject is None or not subject.organizations:
        raise not_found()

    # Search has no single resource to load, so the tenant *is* the resource. A caller in two
    # organizations searches the one their token context resolves to first; the policy still runs
    # against that organization, and rows still come back through its row policy.
    organization_id = subject.organizations[0]
    resource = ResourceContext(
        type="organization", id=organization_id, organization_id=organization_id, attributes={}
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=subject,
        action="customer.search",
        resource=resource,
        resource_type="organization",
        resource_id=organization_id,
    )

    page = scope.customers.search(
        query=q,
        user_id=auth.subject.user_id,
        organization_id=auth.organization_id,
        roles=auth.subject.roles_in(auth.organization_id),
        limit=clamp_limit(limit, auth.decision.max_results),
        cursor=cursor,
    )

    results = [CustomerSummary(**auth.minimize(row)) for row in page.rows]
    scope.pipeline.record_success(
        request_id=scope.request_id, auth=auth, action="customer.search"
    )
    return CustomerSearchResponse(results=results, next_cursor=page.next_cursor)


@router.get(
    "/customers/{customer_ref}",
    operation_id="get_customer",
    summary="Get one customer record the authenticated user may see",
    response_model=CustomerResponse,
    response_model_exclude_none=True,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        503: {"description": "Service unavailable"},
    },
)
def get_customer(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    customer_ref: Annotated[
        str,
        Path(
            pattern=CUSTOMER_REF_PATTERN,
            min_length=8,
            max_length=16,
            description="Customer reference in the form CUS-nnnn",
            examples=["CUS-4001"],
        ),
    ],
) -> CustomerResponse:
    attributes = scope.customers.lookup_attributes(
        customer_ref=customer_ref,
        organization_ids=scope.subject.organizations if scope.subject else [],
    )

    resource = (
        ResourceContext(
            type="customer",
            id=attributes.external_ref,
            organization_id=attributes.organization_id,
            # sensitivity drives the field obligation, so it must come from the database row.
            attributes={"sensitivity": attributes.sensitivity},
        )
        if attributes
        else None
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=scope.subject,
        action="customer.read",
        resource=resource,
        resource_type="customer",
        resource_id=customer_ref,
    )

    record = scope.customers.read_authorized(
        customer_ref=customer_ref,
        user_id=auth.subject.user_id,
        organization_id=auth.organization_id,
        roles=auth.subject.roles_in(auth.organization_id),
    )
    if record is None:
        raise not_found()

    scope.pipeline.record_success(request_id=scope.request_id, auth=auth, action="customer.read")
    return CustomerResponse(**auth.minimize(dict(record)))
