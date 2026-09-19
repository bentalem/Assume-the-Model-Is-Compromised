"""Database access for the Range.

The connection is `sp_range_role`, which holds no privilege on any table in `app`. Everything this
module can do is a call to a function in the `range` schema, and that list is fixed by migration
0010. If a future challenge needs to see something new, the change is a reviewed migration adding a
function — not a wider grant, and never a statement composed here.

There is no query interface in this module and there will not be one. The lab's first rule is that
the model never gets a generic tool; the Range is built by the same people to the same standard.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row

logger = logging.getLogger("supportpilot.range.db")


def _password() -> str:
    path = os.environ.get("RANGE_DB_PASSWORD_FILE", "/run/secrets/range_db_password")
    return Path(path).read_text(encoding="utf-8").strip()


def dsn() -> str:
    host = os.environ.get("DATABASE_HOST", "postgres")
    port = os.environ.get("DATABASE_PORT", "5432")
    name = os.environ.get("DATABASE_NAME", "supportpilot")
    user = os.environ.get("RANGE_DB_USER", "sp_range_role")
    return f"host={host} port={port} dbname={name} user={user} password={_password()}"


def _call(function: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Call one function in the `range` schema and return its rows.

    `function` is never taken from a request. Callers pass a literal from this module, and the
    arguments go through psycopg's parameter binding. A connection per call is deliberate: the
    Range serves one person, the volume is trivial, and a pool would add a pooled-session state
    problem for no benefit — which is the failure mode challenge 2.2 exists to teach.
    """
    with connect(dsn(), autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(params))
            cur.execute(f"SELECT * FROM range.{function}({placeholders})", params)
            return list(cur.fetchall())


def record_event(request_id: str, action: str, mutation_id: str, decision: str, reason: str) -> None:
    """Write the Range's own action to the lab's audit trail, as `actor_type='range'`.

    A learner working challenge 7.1 goes into that trail looking for a request and finds their own
    arming beside it. That is the point: the service with the most authority here is also the one
    whose actions are hardest to miss.
    """
    _call("record_event", (request_id, action, mutation_id, decision, reason))


def table_security(table: str) -> dict[str, Any] | None:
    rows = _call("table_security", (table,))
    return rows[0] if rows else None


def all_table_security() -> list[dict[str, Any]]:
    return _call("all_table_security")


def role_attributes() -> list[dict[str, Any]]:
    return _call("role_attributes")


def healthy() -> tuple[bool, str]:
    """Can the Range reach its own schema? Reported by /healthz, never guessed."""
    try:
        rows = all_table_security()
    except Exception as exc:  # noqa: BLE001 — the reason is what the operator needs
        return False, f"{type(exc).__name__}: {exc}".split("\n")[0][:200]
    return True, f"{len(rows)} table(s) visible in app"
