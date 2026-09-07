"""Action requests: proposal, status, and approval decisions.

The API's whole role in a sensitive action is to *record an intention* and, separately, to record an
independent decision about it. It never executes the effect — that is the worker's job, behind the
approval — and there is no method in this module that could.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg

from ..actions.state import ActionState, payload_hash
from ..audit.writer import AuditEvent, AuditWriter
from ..db import Database

#: How long an approval stays usable. Short by design: an approval is a statement about a situation,
#: and situations change (SP-OPS-001 §6, "Approval expires").
DEFAULT_EXPIRY = timedelta(hours=24)


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    state: str
    expires_at: datetime


@dataclass(frozen=True)
class ActionStatus:
    action_id: str
    action_type: str
    state: str
    amount: str | None
    currency: str | None
    created_at: datetime
    decided_at: datetime | None
    completed_at: datetime | None
    provider_reference: str | None


class DuplicateDecision(Exception):
    """A decision already exists for this action."""


class SelfApprovalRefused(Exception):
    """The database trigger refused: requester and approver are the same person."""


class ActionNotApprovable(Exception):
    """The action is absent, expired, or not awaiting approval."""


_INSERT_REQUEST = """
INSERT INTO app.action_requests (
    organization_id, requester_id, action_type, resource_type, resource_id,
    payload, payload_hash, state, risk_level, expires_at
) VALUES (
    %(organization_id)s::uuid, %(requester_id)s::uuid, %(action_type)s,
    %(resource_type)s, %(resource_id)s, %(payload)s::jsonb, %(payload_hash)s,
    'PROPOSED', %(risk_level)s, %(expires_at)s
)
RETURNING id::text AS id, expires_at
"""

# PROPOSED -> PENDING_APPROVAL. The row policy allows the API exactly this move and no other.
_MOVE_TO_PENDING = """
UPDATE app.action_requests
SET state = 'PENDING_APPROVAL', updated_at = now()
WHERE id = %s::uuid AND state = 'PROPOSED'
RETURNING id::text AS id, state
"""

_READ_STATUS = """
SELECT r.id::text          AS action_id,
       r.action_type       AS action_type,
       r.state             AS state,
       r.payload ->> 'amount'   AS amount,
       r.payload ->> 'currency' AS currency,
       r.created_at        AS created_at,
       d.decided_at        AS decided_at,
       e.finished_at       AS completed_at,
       e.provider_reference AS provider_reference
FROM app.action_requests r
LEFT JOIN app.approval_decisions d ON d.action_request_id = r.id
LEFT JOIN app.action_jobs j        ON j.action_request_id = r.id
LEFT JOIN app.action_executions e  ON e.job_id = j.id
WHERE r.id = %s::uuid
LIMIT 1
"""

_LOOKUP_FOR_APPROVAL = """
SELECT r.id::text              AS id,
       r.organization_id::text AS organization_id,
       r.requester_id::text    AS requester_id,
       r.action_type           AS action_type,
       r.resource_id           AS resource_id,
       r.payload               AS payload,
       r.payload_hash          AS payload_hash,
       r.state                 AS state,
       r.expires_at            AS expires_at
FROM app.action_requests r
WHERE r.id = %s::uuid
LIMIT 1
"""

_INSERT_DECISION = """
INSERT INTO app.approval_decisions (
    action_request_id, approver_id, decision, approved_hash, comment, policy_version
) VALUES (
    %(action_request_id)s::uuid, %(approver_id)s::uuid, %(decision)s,
    %(approved_hash)s, %(comment)s, %(policy_version)s
)
RETURNING id::text AS id, decided_at
"""

_APPLY_DECISION = """
UPDATE app.action_requests
SET state = %(state)s, updated_at = now()
WHERE id = %(id)s::uuid AND state = 'PENDING_APPROVAL'
RETURNING state
"""

_ENQUEUE = """
INSERT INTO app.action_jobs (action_request_id)
VALUES (%s::uuid)
ON CONFLICT (action_request_id) DO NOTHING
RETURNING id::text AS id
"""


class ActionRepository:
    def __init__(self, database: Database, audit: AuditWriter) -> None:
        self._db = database
        self._audit = audit

    # ---------------------------------------------------------------------------------------
    # Proposal
    # ---------------------------------------------------------------------------------------
    def propose(
        self,
        *,
        request_id: str,
        action_type: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any],
        user_id: str,
        organization_id: str,
        roles: list[str],
        policy_version: str | None,
        expiry: timedelta = DEFAULT_EXPIRY,
    ) -> ProposedAction:
        """Record a proposal and move it to PENDING_APPROVAL, with evidence, in one transaction.

        The hash is computed here, from the payload the server validated — never from anything the
        caller supplies alongside it.
        """
        import json

        digest = payload_hash(payload)
        expires_at = datetime.now(tz=None).astimezone() + expiry

        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles
        ) as cur:
            cur.execute(
                _INSERT_REQUEST,
                {
                    "organization_id": organization_id,
                    "requester_id": user_id,
                    "action_type": action_type,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "payload": json.dumps(payload, sort_keys=True),
                    "payload_hash": digest,
                    "risk_level": "high",
                    "expires_at": expires_at,
                },
            )
            created = cur.fetchone()
            action_id = created["id"]

            cur.execute(_MOVE_TO_PENDING, (action_id,))
            moved = cur.fetchone()
            if moved is None:
                raise ActionNotApprovable("the proposal could not be moved to PENDING_APPROVAL")

            self._audit.record_in(
                cur,
                AuditEvent(
                    request_id=request_id,
                    actor_id=user_id,
                    organization_id=organization_id,
                    action=f"{action_type}.propose",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    decision="succeeded",
                    reason="action_pending_approval",
                    policy_version=policy_version,
                    payload_hash=digest,
                    result_reference=action_id,
                ),
            )

        return ProposedAction(
            action_id=action_id, state=ActionState.PENDING_APPROVAL, expires_at=created["expires_at"]
        )

    # ---------------------------------------------------------------------------------------
    # Status
    # ---------------------------------------------------------------------------------------
    def status(
        self, *, action_id: str, user_id: str, organization_id: str, roles: list[str]
    ) -> ActionStatus | None:
        with self._db.transaction(
            user_id=user_id, organization_id=organization_id, roles=roles, read_only=True
        ) as cur:
            try:
                cur.execute(_READ_STATUS, (action_id,))
            except psycopg.errors.InvalidTextRepresentation:
                # Not a uuid. Indistinguishable from "no such action".
                return None
            row = cur.fetchone()

        if row is None:
            return None
        return ActionStatus(**row)

    def lookup_for_approval(
        self, action_id: str, organization_id: str, user_id: str, roles: list[str]
    ) -> dict[str, Any] | None:
        """Load an action for the approval portal, under the approver's full request context.

        User and roles are required, not optional: the row policy on action_requests shows a row to
        its requester *or* to a manager/approver/auditor, and both arms read request context. With
        only a tenant set, an approver would see nothing — which is correct behaviour from the
        policy's point of view, and a bug in the caller.
        """
        with self._db.transaction(
            organization_id=organization_id, user_id=user_id, roles=roles, read_only=True
        ) as cur:
            try:
                cur.execute(_LOOKUP_FOR_APPROVAL, (action_id,))
            except psycopg.errors.InvalidTextRepresentation:
                return None
            return cur.fetchone()

    # ---------------------------------------------------------------------------------------
    # Decision
    # ---------------------------------------------------------------------------------------
    def decide(
        self,
        *,
        request_id: str,
        action_id: str,
        decision: str,
        approved_hash: str,
        comment: str | None,
        approver_id: str,
        organization_id: str,
        roles: list[str],
        policy_version: str,
    ) -> datetime:
        """Record an approval or rejection, and move the action, in one transaction.

        Enqueues the job in the same transaction on approval, so an approved action cannot exist
        without its queue entry.
        """
        target = ActionState.APPROVED if decision == "approved" else ActionState.REJECTED

        with self._db.transaction(
            user_id=approver_id, organization_id=organization_id, roles=roles
        ) as cur:
            try:
                cur.execute(
                    _INSERT_DECISION,
                    {
                        "action_request_id": action_id,
                        "approver_id": approver_id,
                        "decision": decision,
                        "approved_hash": approved_hash,
                        "comment": comment,
                        "policy_version": policy_version,
                    },
                )
            except psycopg.errors.UniqueViolation:
                raise DuplicateDecision from None
            except psycopg.errors.RaiseException as exc:
                if "separation of duty" in str(exc):
                    raise SelfApprovalRefused from None
                raise
            except psycopg.errors.InsufficientPrivilege:
                # The insert policy refused: wrong role, wrong tenant, expired, or not pending.
                raise ActionNotApprovable from None

            recorded = cur.fetchone()

            cur.execute(_APPLY_DECISION, {"id": action_id, "state": target.value})
            if cur.fetchone() is None:
                raise ActionNotApprovable("the action was not awaiting approval")

            if target is ActionState.APPROVED:
                cur.execute(_ENQUEUE, (action_id,))

            self._audit.record_in(
                cur,
                AuditEvent(
                    request_id=request_id,
                    actor_id=approver_id,
                    organization_id=organization_id,
                    action="refund.approve" if decision == "approved" else "refund.reject",
                    resource_type="action_request",
                    resource_id=action_id,
                    decision="approved" if decision == "approved" else "rejected",
                    reason="independent_approval_recorded",
                    policy_version=policy_version,
                    payload_hash=approved_hash,
                ),
            )

        return recorded["decided_at"]


def decimal_to_string(value: Decimal) -> str:
    """Amounts cross boundaries as strings, never floats."""
    return format(value, "f")
