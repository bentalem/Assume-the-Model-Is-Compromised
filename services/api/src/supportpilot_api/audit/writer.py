"""Audit evidence.

Two ways to write an event, and the difference matters:

* `record_in` writes inside a caller-supplied transaction. Used when the event describes an effect,
  so the effect and its evidence commit or roll back together (SP-ARCH-001 §10, "Audit write
  failure").
* `record` opens its own transaction. Used for denials, where there is no business effect to bind
  to — a denial must be recorded even though nothing else happened.

Neither path ever writes a payload body, a response, or a credential. Only identifiers, decisions,
and hashes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg

from ..db import Database

logger = logging.getLogger(__name__)

_INSERT = """
INSERT INTO app.audit_events (
    request_id, trace_id, actor_type, actor_id, organization_id,
    action, resource_type, resource_id, decision, reason,
    policy_version, payload_hash, result_reference
) VALUES (
    %(request_id)s, %(trace_id)s, %(actor_type)s, %(actor_id)s, %(organization_id)s,
    %(action)s, %(resource_type)s, %(resource_id)s, %(decision)s, %(reason)s,
    %(policy_version)s, %(payload_hash)s, %(result_reference)s
)
"""


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    actor_id: str
    action: str
    decision: str
    reason: str
    actor_type: str = "user"
    trace_id: str | None = None
    organization_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    policy_version: str | None = None
    payload_hash: str | None = None
    result_reference: str | None = None

    def as_params(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "organization_id": self.organization_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "decision": self.decision,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "payload_hash": self.payload_hash,
            "result_reference": self.result_reference,
        }


class AuditWriter:
    def __init__(self, database: Database) -> None:
        self._db = database

    def record_in(self, cursor: psycopg.Cursor[Any], event: AuditEvent) -> None:
        """Write evidence inside an existing transaction.

        Deliberately lets a failure propagate. If the evidence cannot be written, the effect it
        describes must not commit.
        """
        cursor.execute(_INSERT, event.as_params())

    def record(self, event: AuditEvent) -> None:
        """Write a standalone event, used for denials."""
        with self._db.transaction(
            user_id=None, organization_id=event.organization_id
        ) as cur:
            cur.execute(_INSERT, event.as_params())
