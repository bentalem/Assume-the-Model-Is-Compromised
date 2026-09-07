"""Per-request wiring.

`request_scope` is the single entry point for an authenticated route. It verifies the token and
loads the subject *before* a route body runs, so no route can reach a resource without those steps
having happened.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Header, Request

from .auth.tokens import VerifiedToken, bearer_from_header
from .pipeline import Pipeline
from .repositories.memberships import Subject
from .repositories.customers import CustomerRepository
from .repositories.orders import OrderRepository
from .repositories.tickets import TicketRepository


@dataclass(frozen=True)
class RequestScope:
    request_id: str
    token: VerifiedToken
    subject: Subject | None
    pipeline: Pipeline
    orders: OrderRepository
    customers: CustomerRepository
    tickets: TicketRepository


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
    )


def _safe_request_id(value: str | None) -> str:
    if not value:
        return f"req-{uuid.uuid4()}"
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:64]
    return cleaned or f"req-{uuid.uuid4()}"
