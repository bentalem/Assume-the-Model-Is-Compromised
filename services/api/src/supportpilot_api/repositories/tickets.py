"""Ticket reads.

Message bodies here are untrusted external content. This module returns them; it never interprets
them. The `restricted` visibility filter is enforced by the row policy in migration 0006 — the
query below does not repeat it, deliberately, so the test that proves restricted messages are
hidden is testing the database rule rather than a duplicate application check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..db import Database
from .pagination import Page, build_page, decode_cursor


@dataclass(frozen=True)
class TicketAttributes:
    id: str
    organization_id: str
    ticket_number: str
    status: str
    assigned_team: str | None


_LOOKUP = """
SELECT t.id::text              AS id,
       t.organization_id::text AS organization_id,
       t.ticket_number         AS ticket_number,
       t.status                AS status,
       t.assigned_team         AS assigned_team
FROM app.tickets t
WHERE t.ticket_number = %s
LIMIT 1
"""

_READ_TICKET = """
SELECT t.ticket_number  AS ticket_number,
       t.subject        AS subject,
       t.status         AS status,
       t.assigned_team  AS assigned_team,
       t.created_at     AS created_at,
       t.updated_at     AS updated_at,
       c.external_ref   AS customer_ref
FROM app.tickets t
JOIN app.customers c ON c.id = t.customer_id
WHERE t.ticket_number = %s
LIMIT 1
"""

# Messages, oldest first, keyset-paged on (created_at, id).
_READ_MESSAGES = """
SELECT m.id::text     AS id,
       m.author_kind  AS author_kind,
       m.body         AS body,
       m.visibility   AS visibility,
       m.created_at   AS created_at
FROM app.ticket_messages m
JOIN app.tickets t ON t.id = m.ticket_id
WHERE t.ticket_number = %(ticket_number)s
  AND (
        %(after_time)s::timestamptz IS NULL
     OR (m.created_at, m.id) > (%(after_time)s::timestamptz, %(after_id)s::uuid)
  )
ORDER BY m.created_at, m.id
LIMIT %(limit)s
"""


class TicketRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def lookup_attributes(
        self, *, ticket_number: str, organization_ids: list[str]
    ) -> TicketAttributes | None:
        for organization_id in organization_ids:
            with self._db.transaction(organization_id=organization_id, read_only=True) as cur:
                cur.execute(_LOOKUP, (ticket_number,))
                row = cur.fetchone()
            if row:
                return TicketAttributes(
                    id=row["id"],
                    organization_id=row["organization_id"],
                    ticket_number=row["ticket_number"],
                    status=row["status"],
                    assigned_team=row["assigned_team"],
                )
        return None

    def read_authorized(
        self,
        *,
        ticket_number: str,
        user_id: str,
        organization_id: str,
        roles: list[str],
        limit: int,
        cursor: str | None,
    ) -> tuple[dict[str, Any] | None, Page]:
        position = decode_cursor(cursor) or {}

        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles, read_only=True
        ) as cur:
            cur.execute(_READ_TICKET, (ticket_number,))
            ticket = cur.fetchone()
            if ticket is None:
                return None, Page(rows=[], next_cursor=None)

            cur.execute(
                _READ_MESSAGES,
                {
                    "ticket_number": ticket_number,
                    "after_time": position.get("created_at"),
                    "after_id": position.get("id"),
                    "limit": limit + 1,
                },
            )
            rows = cur.fetchall()

        return ticket, build_page(rows, limit, cursor_fields=("created_at", "id"))
