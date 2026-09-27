"""The request scope: a verified token, turned into a principal, for one request.

Order of work, and it matches the API's: reject what the route does not declare → verify the token
→ resolve the principal from the core database. Nothing here reads identity from the request body,
a query parameter or a header other than Authorization. There is no parameter for a user, an
organisation, a role, a channel or an approval anywhere in this service, and that is a property the
verify checks assert against the published action document.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Header, Request

from .errors import invalid_request
from .principal import Principal
from .tokens import VerifiedToken, bearer_from_header

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Scope:
    request_id: str
    token: VerifiedToken
    principal: Principal
    # The application's services, carried on the scope so handlers never reach for a global.
    services: Any


def request_scope(
    request: Request,
    # Hidden from the action document, as in the API: the token arrives by passthrough and the
    # correlation id is infrastructure. Neither is something a model should be told it can set.
    authorization: str | None = Header(default=None, include_in_schema=False),
    x_request_id: str | None = Header(default=None, include_in_schema=False),
) -> Scope:
    services = request.app.state.services
    _reject_unknown_query_parameters(request)
    request_id = _safe_request_id(x_request_id)

    token = services.verifier.verify(bearer_from_header(authorization))
    principal = services.principals.resolve(token.subject)
    return Scope(request_id=request_id, token=token, principal=principal, services=services)


def _reject_unknown_query_parameters(request: Request) -> None:
    """Refuse a query parameter the route does not declare — the API's rule, for the same reason.

    Silence is the worst answer for a caller that cannot see the schema it violated: `recall` with
    a misspelt parameter would otherwise return a clean 200 that means something else.
    """
    route = request.scope.get("route")
    dependant = getattr(route, "dependant", None) if route else None
    if dependant is None:
        return
    declared = {p.alias for p in dependant.query_params}
    for dependency in getattr(dependant, "dependencies", []):
        declared |= {p.alias for p in dependency.query_params}
    unknown = set(request.query_params) - declared
    if unknown:
        logger.info("request_rejected", extra={"path": request.url.path,
                                              "reason": "unknown_query_parameter"})
        raise invalid_request()


def _safe_request_id(value: str | None) -> str:
    if not value:
        return f"mem-{uuid.uuid4()}"
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:64]
    return cleaned or f"mem-{uuid.uuid4()}"
