"""Audit evidence, written in the same transaction as the change it describes.

Every function here takes the cursor of the transaction that is making the change. There is no
separate connection and no "log it afterwards": if the audit insert fails, the change fails with
it, and a memory written with no record of who wrote it cannot exist. That is invariant 9 of the
lab, applied to a new store.
"""

from __future__ import annotations

from typing import Any

import psycopg

from .principal import Principal

_INSERT = """
INSERT INTO mem.audit_events
  (request_id, actor_type, actor_sub, org_id, action, resource_type, resource_id, decision, reason)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def record(
    cur: psycopg.Cursor[dict[str, Any]],
    *,
    request_id: str,
    principal: Principal | None,
    action: str,
    decision: str,
    reason: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_type: str = "user",
) -> None:
    cur.execute(
        _INSERT,
        (
            request_id,
            actor_type,
            principal.subject if principal else None,
            principal.org_id if principal else None,
            action,
            resource_type,
            resource_id,
            decision,
            reason,
        ),
    )
