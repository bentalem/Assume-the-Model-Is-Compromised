"""The Range's access to memory-db (track 9).

The same arrangement as db.py, in a second database. The connection is `mem_range_role`, which owns
nothing, holds no table privilege, and may EXECUTE only the functions in the `range_mem` schema
(memory-db migrations 0006, 0008, 0009, 0010). Every call here names one of those functions with a
literal from registry.py; nothing composes a statement and nothing derived from a request reaches
one.

The memory stack is a compose profile, so it may simply not be running. That is not a fault and not
an unknown state: it is reported as its own exception, and the registry shows those controls as
absent rather than guessing at them — and never as correct.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("supportpilot.range.memdb")


class MemoryStackNotRunning(Exception):
    """memory-db could not be reached: the `memory` profile is not up."""


def _password() -> str:
    path = os.environ.get("RANGE_MEMORY_DB_PASSWORD_FILE", "/run/secrets/range_memory_db_password")
    return Path(path).read_text(encoding="utf-8").strip()


# When memory-db cannot be reached, name resolution alone takes seconds to fail — and one state sweep
# probes eight controls, a reset sweeps more than once, and a page renders on top. So an unreachable
# stack is remembered for a few seconds. Only that: it can make a control read `absent` a little
# longer, never `correct`, and a stack that comes back is read normally once the window passes.
_UNREACHABLE_FOR_SECONDS = 10.0
_unreachable_until = 0.0


def _connect() -> psycopg.Connection:
    global _unreachable_until
    if time.monotonic() < _unreachable_until:
        raise MemoryStackNotRunning("memory-db was unreachable moments ago")
    try:
        return psycopg.connect(
            host=os.environ.get("MEMORY_DB_HOST", "memory-db"),
            port=int(os.environ.get("MEMORY_DB_PORT", "5432")),
            dbname=os.environ.get("MEMORY_DB_NAME", "memory"),
            user=os.environ.get("RANGE_MEMORY_DB_USER", "mem_range_role"),
            password=_password(),
            connect_timeout=3,
            autocommit=True,
            row_factory=dict_row,
            application_name="range",
        )
    except (psycopg.OperationalError, OSError) as exc:
        _unreachable_until = time.monotonic() + _UNREACHABLE_FOR_SECONDS
        raise MemoryStackNotRunning(str(exc).split("\n")[0][:160]) from exc


def select(function: str, *params: str) -> list[dict[str, Any]]:
    """Rows of one `range_mem` function. `function` is a literal from registry.py."""
    with _connect() as conn, conn.cursor() as cur:
        placeholders = ", ".join(["%s"] * len(params))
        cur.execute(f"SELECT * FROM range_mem.{function}({placeholders})", params)
        return list(cur.fetchall())


def scalar(function: str, *params: str) -> Any:
    """The single value of one `range_mem` function."""
    with _connect() as conn, conn.cursor() as cur:
        placeholders = ", ".join(["%s"] * len(params))
        cur.execute(f"SELECT range_mem.{function}({placeholders}) AS value", params)
        row = cur.fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    scalar("set_setting", key, value)


def setting_state(key: str) -> str:
    """`correct`, `armed` or `unknown`, read from memory-db.

    A separate call from any set_setting, always: read in the same statement as the change, the
    setting still shows its old value — a snapshot artifact that once made an armed switch read as
    correct.
    """
    return str(scalar("setting_state", key) or "unknown")


def get_setting(key: str) -> str | None:
    value = scalar("get_setting", key)
    return None if value is None else str(value)


def leftovers() -> dict[str, int]:
    return {row["kind"]: int(row["remaining"]) for row in select("leftovers")}
