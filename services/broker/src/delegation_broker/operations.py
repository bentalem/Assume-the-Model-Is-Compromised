"""Which API operation a gateway call is, and so which scope it needs.

Resolved from the method and path of the call — the one thing the agent platform cannot avoid
telling us — and never from a body, a header or anything the model wrote. The table is the API's
action document, operation by operation, with the policy action each one is decided as. A test
compares it with `openapi/supportpilot-actions.json`, so a new operation in the API is a failing
test here rather than a path the gateway quietly does not know.

A call that matches no row is refused, not forwarded. The gateway is a route to seven operations,
not a proxy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# One path segment the way the API's own patterns allow them: letters, digits and hyphens, bounded.
_SEGMENT = r"[A-Za-z0-9-]{1,64}"


@dataclass(frozen=True)
class Operation:
    method: str
    template: str
    operation_id: str
    action: str
    pattern: re.Pattern[str]


def _op(method: str, template: str, operation_id: str, action: str) -> Operation:
    regex = "^" + re.sub(r"\{[a-z_]+\}", _SEGMENT, template) + "$"
    return Operation(method, template, operation_id, action, re.compile(regex))


OPERATIONS: tuple[Operation, ...] = (
    _op("GET", "/v1/orders/{order_number}", "get_order", "order.read"),
    _op("GET", "/v1/customers", "search_customers", "customer.search"),
    _op("GET", "/v1/customers/{customer_ref}", "get_customer", "customer.read"),
    _op("GET", "/v1/tickets/{ticket_number}", "get_ticket", "ticket.read"),
    _op("POST", "/v1/tickets/{ticket_number}/notes", "add_internal_note", "note.create"),
    _op("POST", "/v1/actions/refunds", "propose_refund", "refund.propose"),
    _op("GET", "/v1/actions/{action_id}", "get_action_status", "action.read"),
)


def resolve(method: str, path: str) -> Operation | None:
    for operation in OPERATIONS:
        if operation.method == method.upper() and operation.pattern.match(path):
            return operation
    return None
