"""Order reads.

Named columns, bound parameters, `LIMIT` on every statement (SP-DATA-001 §8). There is no query
builder and no dynamic SQL: each statement is a module-level literal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..db import Database


@dataclass(frozen=True)
class OrderAttributes:
    """The trusted resource attributes, loaded before the policy call.

    `organization_id` here is the authority on which tenant the order belongs to. It comes from the
    database, never from the request (SP-DATA-001 §3).
    """

    id: str
    organization_id: str
    order_number: str
    status: str
    currency: str
    total_amount: Decimal


@dataclass(frozen=True)
class OrderRecord:
    order_number: str
    status: str
    currency: str
    total_amount: Decimal
    placed_at: datetime
    updated_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "order_number": self.order_number,
            "status": self.status,
            "currency": self.currency,
            "total_amount": str(self.total_amount),
            "placed_at": self.placed_at,
            "updated_at": self.updated_at,
        }


# Resource lookup. Runs WITHOUT tenant context, because the tenant is what it is establishing —
# so it is scoped by the caller's memberships instead. An order outside every membership returns no
# row, which the route reports as not_found.
_LOOKUP_ATTRIBUTES = """
SELECT o.id::text              AS id,
       o.organization_id::text AS organization_id,
       o.order_number          AS order_number,
       o.status                AS status,
       o.currency              AS currency,
       o.total_amount          AS total_amount
FROM app.orders o
WHERE o.order_number = %(order_number)s
  AND o.organization_id = ANY(%(organization_ids)s::uuid[])
LIMIT 1
"""

# The authorized read. Runs under full tenant context, so the row policy filters it a second time.
_SELECT_ORDER = """
SELECT order_number, status, currency, total_amount, placed_at, updated_at
FROM app.orders
WHERE order_number = %s
LIMIT 1
"""


class OrderRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def find_for_subject(
        self, order_number: str, organization_ids: list[str]
    ) -> OrderAttributes | None:
        """Load trusted attributes for the policy input.

        Each of the caller's tenants is probed under its own request context, so the row policy
        applies to every probe rather than being bypassed by a context-free lookup. A tenant the
        caller has no membership in is never queried at all, so this cannot be used to test whether
        an order exists elsewhere.
        """
        for organization_id in organization_ids:
            with self._db.transaction(organization_id=organization_id, read_only=True) as cur:
                cur.execute(
                    _LOOKUP_ATTRIBUTES,
                    {"order_number": order_number, "organization_ids": [organization_id]},
                )
                row = cur.fetchone()
            if row:
                return OrderAttributes(
                    id=row["id"],
                    organization_id=row["organization_id"],
                    order_number=row["order_number"],
                    status=row["status"],
                    currency=row["currency"],
                    total_amount=row["total_amount"],
                )
        return None

    def read_authorized(
        self, *, order_number: str, user_id: str, organization_id: str
    ) -> OrderRecord | None:
        """The authorized read, under full request context."""
        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, read_only=True
        ) as cur:
            cur.execute(_SELECT_ORDER, (order_number,))
            row = cur.fetchone()

        if not row:
            return None
        return OrderRecord(
            order_number=row["order_number"],
            status=row["status"],
            currency=row["currency"],
            total_amount=row["total_amount"],
            placed_at=row["placed_at"],
            updated_at=row["updated_at"],
        )
