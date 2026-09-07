"""Database access.

Two rules govern everything in this module:

1. **Request context is transaction-local.** `SET LOCAL` inside an explicit transaction, so a pooled
   connection cannot carry one user's identity into the next request (`TS4-01`, `TS4-02`). There is
   deliberately no helper that sets context outside a transaction — the unsafe call does not exist.
2. **Parameters, never interpolation.** psycopg binds server-side; SQL text is always a literal in
   the repository modules.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .errors import unavailable

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._pool = ConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
            # A returned connection must be clean. SET LOCAL is already rolled back with the
            # transaction; this is the second line of defence behind that.
            reset=_reset_connection,
        )

    def open(self, timeout: float = 15.0) -> None:
        self._pool.open(wait=True, timeout=timeout)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(
        self,
        *,
        user_id: str | None = None,
        organization_id: str | None = None,
        roles: list[str] | None = None,
        read_only: bool = False,
    ) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
        """Run a block inside one transaction with request context set locally.

        Omitting `organization_id` is meaningful, not an oversight: the membership lookup runs with
        only `app.user_id` set, because the tenant is not known until that lookup returns. Business
        tables are invisible in that state, which is exactly right.

        `roles` are the caller's memberships **for the tenant being accessed**, loaded server-side.
        Row policies that depend on a role (restricted ticket messages, for one) read them through
        app.current_roles(). Omitting them means no role is held, so those policies fail closed.
        """
        try:
            with self._pool.connection() as conn:
                conn.read_only = read_only
                with conn.transaction():
                    with conn.cursor() as cur:
                        # set_config(..., is_local => true) is SET LOCAL with a bound parameter, so
                        # the identifier never reaches SQL as text.
                        cur.execute(
                            "SELECT set_config('app.user_id', %s, true)",
                            (user_id or "",),
                        )
                        cur.execute(
                            "SELECT set_config('app.organization_id', %s, true)",
                            (organization_id or "",),
                        )
                        # A role name is validated at the source (a CHECK constraint on
                        # app.memberships), so the comma-separated form cannot smuggle a separator.
                        cur.execute(
                            "SELECT set_config('app.roles', %s, true)",
                            (",".join(sorted(roles or [])),),
                        )
                        yield cur
        except psycopg.OperationalError:
            # Connection-level failure: the database is unreachable or refused us.
            logger.error("database_unavailable", exc_info=True)
            raise unavailable() from None
        except psycopg.Error:
            # Any other database error is mapped to a stable API error. The message, the SQLSTATE,
            # and the statement never reach the caller.
            logger.error("database_error", exc_info=True)
            raise unavailable() from None

    def healthy(self) -> bool:
        try:
            with self._pool.connection(timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False


def _reset_connection(conn: psycopg.Connection[Any]) -> None:
    """Clear any session state before a connection returns to the pool.

    `SET LOCAL` is already undone when the transaction ends; this is the second line of defence
    behind that.

    The rollback and the autocommit switch both matter. psycopg opens an implicit transaction for
    any statement when autocommit is off, so running `RESET ALL` directly would hand the connection
    back in INTRANS — and the pool discards a connection left in a transaction, silently turning
    the pool into "reconnect on every request".
    """
    conn.rollback()
    previous = conn.autocommit
    conn.autocommit = True
    try:
        conn.execute("RESET ALL")
    finally:
        conn.autocommit = previous
