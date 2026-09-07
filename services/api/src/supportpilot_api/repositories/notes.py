"""Internal note writes.

The first path that changes state, so two rules from the baseline become concrete here:

* **Authorship is server-derived.** `author_id` comes from the verified subject. It is not a
  parameter, and the insert policy in migration 0007 refuses any other value.
* **Business state and its evidence commit together.** The note and its audit event are written in
  one transaction, so a failed audit write rolls the note back (SP-ARCH-001 §10).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import psycopg

from ..audit.writer import AuditEvent, AuditWriter
from ..db import Database


@dataclass(frozen=True)
class CreatedNote:
    note_id: str
    created_at: datetime


class StaleTicketError(Exception):
    """The ticket is not in the state the caller expected."""


# The expected-state check is part of the INSERT, not a separate SELECT. A read-then-write would
# leave a window in which the ticket changes between the two statements; here the condition and the
# write are one atomic operation (SP-DATA-001 §8, "Write statements include expected current
# state").
_INSERT_NOTE = """
INSERT INTO app.internal_notes (organization_id, ticket_id, author_id, body)
SELECT t.organization_id, t.id, %(author_id)s::uuid, %(body)s
FROM app.tickets t
WHERE t.ticket_number = %(ticket_number)s
  AND (%(expected_status)s::text IS NULL OR t.status = %(expected_status)s)
RETURNING id::text AS id, created_at
"""


class NoteRepository:
    def __init__(self, database: Database, audit: AuditWriter) -> None:
        self._db = database
        self._audit = audit

    def create(
        self,
        *,
        request_id: str,
        ticket_number: str,
        body: str,
        expected_status: str | None,
        user_id: str,
        organization_id: str,
        roles: list[str],
        policy_version: str | None,
        resource_id: str,
    ) -> CreatedNote:
        """Create a note and its audit event in one transaction.

        Raises StaleTicketError when the ticket does not exist in the caller's tenant or is not in
        the expected state. Those two are deliberately indistinguishable to the caller: reporting
        them differently would tell an unauthorized caller whether a ticket exists.
        """
        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles
        ) as cur:
            try:
                cur.execute(
                    _INSERT_NOTE,
                    {
                        "author_id": user_id,
                        "body": body,
                        "ticket_number": ticket_number,
                        "expected_status": expected_status,
                    },
                )
            except psycopg.errors.InsufficientPrivilege:
                # The row policy refused the insert — a tenant or authorship mismatch that the
                # application layer failed to catch. Treat it as a stale/absent ticket, and let the
                # denial be recorded rather than surfacing a database error.
                raise StaleTicketError from None

            row = cur.fetchone()
            if row is None:
                # No ticket matched the number *and* the expected status, under this tenant.
                raise StaleTicketError

            # Same transaction: if this fails, the note does not exist either.
            self._audit.record_in(
                cur,
                AuditEvent(
                    request_id=request_id,
                    actor_id=user_id,
                    organization_id=organization_id,
                    action="note.create",
                    resource_type="ticket",
                    resource_id=resource_id,
                    decision="succeeded",
                    reason="note_created",
                    policy_version=policy_version,
                    result_reference=row["id"],
                ),
            )

            return CreatedNote(note_id=row["id"], created_at=row["created_at"])
