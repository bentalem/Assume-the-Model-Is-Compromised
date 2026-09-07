"""Customer reads.

Search is the tool with the widest blast radius, so it is the most constrained: a mandatory page
size, a keyset cursor, a fixed sort, and a narrow column list. There is no "return everything" mode
and no caller-supplied ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..db import Database
from .pagination import Page, build_page, decode_cursor


@dataclass(frozen=True)
class CustomerAttributes:
    """Trusted attributes for the policy input."""

    id: str
    organization_id: str
    external_ref: str
    sensitivity: str


# Search. Sorted by (lower(full_name), id) so the keyset cursor is stable and total: the id
# tie-breaks names that repeat, which an unstable sort would silently skip or duplicate.
_SEARCH = """
SELECT c.id::text          AS id,
       c.external_ref      AS customer_ref,
       c.full_name         AS full_name,
       c.assigned_team     AS assigned_team,
       lower(c.full_name)  AS sort_name
FROM app.customers c
WHERE c.full_name ILIKE %(pattern)s
  AND (
        %(after_name)s::text IS NULL
     OR (lower(c.full_name), c.id) > (%(after_name)s::text, %(after_id)s::uuid)
  )
ORDER BY lower(c.full_name), c.id
LIMIT %(limit)s
"""

_LOOKUP = """
SELECT c.id::text              AS id,
       c.organization_id::text AS organization_id,
       c.external_ref          AS external_ref,
       c.sensitivity           AS sensitivity
FROM app.customers c
WHERE c.external_ref = %s
LIMIT 1
"""

_READ = """
SELECT c.external_ref   AS customer_ref,
       c.full_name      AS full_name,
       c.email          AS email,
       c.assigned_team  AS assigned_team,
       (SELECT count(*) FROM app.tickets t
         WHERE t.customer_id = c.id AND t.status IN ('open', 'pending')) AS open_ticket_count
FROM app.customers c
WHERE c.external_ref = %s
LIMIT 1
"""


class CustomerRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    def search(
        self,
        *,
        query: str,
        user_id: str,
        organization_id: str,
        roles: list[str],
        limit: int,
        cursor: str | None,
    ) -> Page:
        position = decode_cursor(cursor) or {}
        # ILIKE with the wildcards added here, not by the caller: a caller-supplied '%' would turn
        # a name search into a full-table scan of the tenant.
        pattern = f"%{query}%"

        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles, read_only=True
        ) as cur:
            cur.execute(
                _SEARCH,
                {
                    "pattern": pattern,
                    "after_name": position.get("sort_name"),
                    "after_id": position.get("id"),
                    "limit": limit + 1,  # over-fetch by one to detect a further page
                },
            )
            rows = cur.fetchall()

        return build_page(rows, limit, cursor_fields=("sort_name", "id"))

    def lookup_attributes(
        self, *, customer_ref: str, organization_ids: list[str]
    ) -> CustomerAttributes | None:
        """Load trusted attributes, probing each of the caller's tenants under its own context."""
        for organization_id in organization_ids:
            with self._db.transaction(organization_id=organization_id, read_only=True) as cur:
                cur.execute(_LOOKUP, (customer_ref,))
                row = cur.fetchone()
            if row:
                return CustomerAttributes(
                    id=row["id"],
                    organization_id=row["organization_id"],
                    external_ref=row["external_ref"],
                    sensitivity=row["sensitivity"],
                )
        return None

    def read_authorized(
        self, *, customer_ref: str, user_id: str, organization_id: str, roles: list[str]
    ) -> dict[str, Any] | None:
        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles, read_only=True
        ) as cur:
            cur.execute(_READ, (customer_ref,))
            return cur.fetchone()
