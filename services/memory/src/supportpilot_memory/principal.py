"""Who is calling: organisation and roles, from the core database, on every request.

A verified token says who someone is. It does not say what they may do, and it never says which
organisation they are acting in — a token claim for that would be the caller telling us, which is
exactly what challenge 1.4 refuses. So the memory service asks the core database, through the one
function it may call (`app.resolve_subject`, migration 0029 grants it), and uses the answer for
this request only.

Never cached across requests. Challenge 1.3 is about a revoked role that keeps working because
something remembered it; a memory layer that cached principals would be that bug in the one service
whose whole subject is what should and should not be remembered.

A person with active memberships in more than one organisation is refused rather than guessed
about. Nothing in a request may choose the tenant, so there is nothing to choose it with — and
picking one would be the service deciding, silently, whose memories to show.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .errors import ApiError, not_found, unavailable

logger = logging.getLogger(__name__)

_LOOKUP = "SELECT user_id, organization_id, role FROM app.resolve_subject(%s)"


@dataclass(frozen=True)
class Principal:
    subject: str
    user_id: str
    org_id: str
    roles: tuple[str, ...]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def ambiguous_tenant() -> ApiError:
    """More than one organisation, and nothing in the request may say which."""
    return ApiError(403, "ambiguous_tenant")


class PrincipalResolver:
    def __init__(self, dsn: str, *, max_size: int = 4) -> None:
        self._pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=False,
        )

    def open(self, timeout: float = 15.0) -> None:
        self._pool.open(wait=True, timeout=timeout)

    def close(self) -> None:
        self._pool.close()

    def resolve(self, subject: str) -> Principal:
        try:
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.execute(_LOOKUP, (subject,))
                rows = cur.fetchall()
        except psycopg.Error:
            # The identity store is unreachable. That is a refusal, never "proceed without a
            # tenant": a memory layer that answered without knowing whose memories to show would
            # have to pick, and every choice it could make is wrong for somebody.
            logger.error("principal_lookup_unavailable", exc_info=True)
            raise unavailable() from None

        memberships = [row for row in rows if row["organization_id"] is not None]
        if not memberships:
            # Unknown subject, a deactivated user, or someone with no active membership: all the
            # same answer, and the same one the API gives for a resource you may not see.
            raise not_found()

        organisations = {str(row["organization_id"]) for row in memberships}
        if len(organisations) != 1:
            logger.info("principal_ambiguous", extra={"organisations": len(organisations)})
            raise ambiguous_tenant()

        return Principal(
            subject=subject,
            user_id=str(memberships[0]["user_id"]),
            org_id=organisations.pop(),
            roles=tuple(sorted({row["role"] for row in memberships})),
        )

    def healthy(self) -> bool:
        try:
            with self._pool.connection(timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False
