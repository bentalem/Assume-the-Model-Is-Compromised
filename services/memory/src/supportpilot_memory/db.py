"""memory-db access.

The same two rules as the API's database module, and for the same reasons:

1. **Request context is transaction-local.** `set_config(..., true)` — `SET LOCAL` with a bound
   parameter — inside an explicit transaction, in the same transaction as the query. Never a
   session-level `SET` on a pooled connection. Challenge 2.2 is the whole argument, and it applies
   to a memory store at least as much as to the API: what would leak here between two users on one
   pooled connection is not an order, it is a conversation.
2. **Parameters, never interpolation.** SQL text is a literal in these modules.

There is deliberately no helper that sets context outside a transaction. The unsafe call does not
exist, so it cannot be made by mistake.
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
from .principal import Principal

logger = logging.getLogger(__name__)


class MemoryDatabase:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._pool = ConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
            reset=_reset_connection,
        )

    def open(self, timeout: float = 15.0) -> None:
        self._pool.open(wait=True, timeout=timeout)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(self, principal: Principal | None) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
        """One transaction, with the caller's context set locally for its duration.

        `principal=None` sets no context at all, which is meaningful: every policy compares against
        these values, a comparison with NULL is never true, and so nothing is visible. A refusal
        written to the audit trail before a principal was known runs in that state.
        """
        try:
            with self._pool.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT set_config('mem.user_sub', %s, true), "
                            "       set_config('mem.org_id', %s, true), "
                            "       set_config('mem.roles', %s, true)",
                            (
                                principal.subject if principal else "",
                                principal.org_id if principal else "",
                                # Role names come from a CHECK-constrained column in the core
                                # database, so a comma cannot be smuggled into one.
                                ",".join(principal.roles) if principal else "",
                            ),
                        )
                        yield cur
        except psycopg.errors.RaiseException:
            # A trigger refused the write — separation of duty on a rule decision. Re-raised as
            # itself, so the handler can answer 403 rather than calling it an outage.
            raise
        except psycopg.errors.InsufficientPrivilege:
            # A row-level security WITH CHECK refused the write: the store said no. That is a
            # decision, not an outage, and the caller should learn that it was refused.
            raise
        except psycopg.OperationalError:
            logger.error("memory_db_unavailable", exc_info=True)
            raise unavailable() from None
        except psycopg.Error:
            logger.error("memory_db_error", exc_info=True)
            raise unavailable() from None

    def healthy(self) -> bool:
        try:
            with self._pool.connection(timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False


def _reset_connection(conn: psycopg.Connection[Any]) -> None:
    """Clear session state before a connection returns to the pool.

    The transaction-local settings are already gone when the transaction ends; this is the second
    line of defence behind that, and it is copied from the API because the reasoning is identical.
    The rollback and the autocommit switch both matter: `RESET ALL` run with autocommit off would
    open an implicit transaction, and the pool discards a connection left in one.
    """
    conn.rollback()
    previous = conn.autocommit
    conn.autocommit = True
    try:
        conn.execute("RESET ALL")
    finally:
        conn.autocommit = previous
