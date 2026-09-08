"""Per-request wiring.

`request_scope` is the single entry point for an authenticated route. It verifies the token and
loads the subject *before* a route body runs, so no route can reach a resource without those steps
having happened.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Header, Request

import logging

from .auth.tokens import VerifiedToken, bearer_from_header
from .errors import invalid_request
from .pipeline import Pipeline
from .repositories.memberships import Subject
from .repositories.actions import ActionRepository
from .repositories.notes import NoteRepository
from .repositories.customers import CustomerRepository
from .repositories.orders import OrderRepository
from .repositories.tickets import TicketRepository


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestScope:
    request_id: str
    token: VerifiedToken
    subject: Subject | None
    pipeline: Pipeline
    orders: OrderRepository
    customers: CustomerRepository
    tickets: TicketRepository
    notes: NoteRepository
    actions: ActionRepository


def request_scope(
    request: Request,
    # include_in_schema=False keeps these out of the action document. Onyx supplies the bearer token
    # through passthrough authentication and the correlation id is infrastructure; neither is
    # something the model should be told it can set. A model-visible Authorization parameter would
    # invite exactly the wrong behavior.
    authorization: str | None = Header(default=None, include_in_schema=False),
    x_request_id: str | None = Header(default=None, include_in_schema=False),
) -> RequestScope:
    services = request.app.state.services

    _reject_unknown_query_parameters(request)

    # A caller-supplied correlation id is accepted but never trusted as data: it is bounded and
    # stripped of anything that could forge a log line.
    request_id = _safe_request_id(x_request_id)

    raw_token = bearer_from_header(authorization)
    token = services.verifier.verify(raw_token)

    subject = services.memberships.load_subject(token.subject, token.authentication_level)

    return RequestScope(
        request_id=request_id,
        token=token,
        subject=subject,
        pipeline=services.pipeline,
        orders=services.orders,
        customers=services.customers,
        tickets=services.tickets,
        notes=services.notes,
        actions=services.actions,
    )


def _reject_unknown_query_parameters(request: Request) -> None:
    """Refuse a query parameter the route does not declare.

    HTTP convention is to ignore unknown parameters. For a tool API that convention is a trap: a
    model sending `include_item=true` (no plural) would get a clean 200 with no items and reasonably
    conclude it had asked for them. Silence is the worst possible answer to give a caller that
    cannot see the schema it violated.

    Rejecting is also the same rule the response models already follow — `extra="forbid"` — applied
    to the request side, so the contract is strict in both directions.
    """
    route = request.scope.get("route")
    declared = {p.alias for p in getattr(route, "dependant", None).query_params} if route else None
    if declared is None:
        return

    # Dependencies declare their own parameters; collect those too rather than special-casing.
    for dependency in getattr(route.dependant, "dependencies", []):
        declared |= {p.alias for p in dependency.query_params}

    unknown = set(request.query_params) - declared
    if unknown:
        logger.info(
            "request_rejected",
            extra={"path": request.url.path, "reason": "unknown_query_parameter"},
        )
        raise invalid_request()


def _safe_request_id(value: str | None) -> str:
    if not value:
        return f"req-{uuid.uuid4()}"
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:64]
    return cleaned or f"req-{uuid.uuid4()}"
