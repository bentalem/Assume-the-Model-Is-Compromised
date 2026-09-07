"""Job claim and execution.

The order of checks here is the security design, not defensive habit. Before anything reaches a
provider the worker independently re-establishes that:

  1. it holds an exclusive lease on the job (no other worker is doing this);
  2. an approval decision exists, and is an approval;
  3. the approver was not the requester;
  4. the approval has not expired;
  5. the hash the approver approved still matches the payload about to execute;
  6. no execution row exists for this idempotency key.

It re-checks all of this even though the API and the approval portal already did. The worker is the
last thing before money moves, and it is the only component that can see the state as it is at the
moment of execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg

from ..adapters.refund import Outcome, RefundAdapter

logger = logging.getLogger("supportpilot.worker.jobs")


class RefusedToExecute(Exception):
    """A pre-execution check failed. The job is not attempted."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    action_request_id: str
    action_type: str
    payload: dict[str, Any]
    payload_hash: str
    state: str
    expires_at: datetime
    requester_id: str
    organization_id: str
    attempts: int


# The atomic claim. FOR UPDATE SKIP LOCKED is what lets several workers run without two of them
# taking the same job: each skips rows another has locked rather than blocking on them.
#
# The WHERE clause also reclaims jobs whose lease expired — a worker that crashed mid-execution
# leaves EXECUTING behind, and without this the job would be stuck forever.
_CLAIM = """
UPDATE app.action_jobs
SET state = 'EXECUTING',
    lease_owner = %(owner)s,
    lease_expires_at = now() + make_interval(secs => %(lease_seconds)s),
    attempts = attempts + 1
WHERE id = (
    SELECT j.id
    FROM app.action_jobs j
    WHERE (
            (j.state = 'QUEUED' AND j.available_at <= now())
         OR (j.state = 'EXECUTING' AND j.lease_expires_at < now())
          )
      AND j.attempts < j.max_attempts
    ORDER BY j.available_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id::text AS job_id, action_request_id::text AS action_request_id, attempts
"""

_LOAD_ACTION = """
SELECT r.id::text              AS action_request_id,
       r.organization_id::text AS organization_id,
       r.requester_id::text    AS requester_id,
       r.action_type           AS action_type,
       r.payload               AS payload,
       r.payload_hash          AS payload_hash,
       r.state                 AS state,
       r.expires_at            AS expires_at
FROM app.action_requests r
WHERE r.id = %s::uuid
"""

_LOAD_DECISION = """
SELECT approver_id::text AS approver_id,
       decision,
       approved_hash,
       decided_at
FROM app.approval_decisions
WHERE action_request_id = %s::uuid
"""

_RESERVE_IDEMPOTENCY = """
INSERT INTO app.action_executions (job_id, idempotency_key, provider, outcome, detail)
VALUES (%(job_id)s::uuid, %(key)s, %(provider)s, 'ambiguous', 'reserved before provider call')
RETURNING id::text AS id
"""

_COMPLETE_EXECUTION = """
UPDATE app.action_executions
SET outcome = %(outcome)s,
    provider_reference = %(reference)s,
    detail = %(detail)s,
    finished_at = now()
WHERE idempotency_key = %(key)s
RETURNING id::text AS id
"""

_FINISH_JOB = """
UPDATE app.action_jobs
SET state = %(state)s,
    lease_owner = NULL,
    lease_expires_at = NULL,
    last_error = %(error)s,
    available_at = CASE WHEN %(state)s = 'QUEUED'
                        THEN now() + make_interval(secs => %(backoff)s)
                        ELSE available_at END
WHERE id = %(job_id)s::uuid
"""

_SET_ACTION_STATE = """
UPDATE app.action_requests
SET state = %(state)s, updated_at = now()
WHERE id = %(id)s::uuid
"""

_AUDIT = """
INSERT INTO app.audit_events (
    request_id, actor_type, actor_id, organization_id, action,
    resource_type, resource_id, decision, reason, payload_hash, result_reference
) VALUES (
    %(request_id)s, 'workload', %(actor_id)s, %(organization_id)s::uuid, %(action)s,
    'action_request', %(resource_id)s, %(decision)s, %(reason)s, %(payload_hash)s, %(reference)s
)
"""


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def idempotency_key(action_id: str, hash_value: str) -> str:
    return f"{action_id}:{hash_value[:32]}"


class JobProcessor:
    def __init__(
        self,
        connection: psycopg.Connection,
        adapter: RefundAdapter,
        *,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> None:
        self._conn = connection
        self._adapter = adapter
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds

    # ---------------------------------------------------------------------------------------
    def claim(self) -> ClaimedJob | None:
        """Take one job, exclusively, or return None."""
        with self._conn.cursor() as cur:
            cur.execute(
                _CLAIM, {"owner": self._worker_id, "lease_seconds": self._lease_seconds}
            )
            claimed = cur.fetchone()
            if claimed is None:
                self._conn.commit()
                return None

            cur.execute(_LOAD_ACTION, (claimed["action_request_id"],))
            action = cur.fetchone()

        self._conn.commit()

        if action is None:
            raise RefusedToExecute("action_request_missing")

        return ClaimedJob(
            job_id=claimed["job_id"],
            action_request_id=action["action_request_id"],
            action_type=action["action_type"],
            payload=action["payload"],
            payload_hash=action["payload_hash"],
            state=action["state"],
            expires_at=action["expires_at"],
            requester_id=action["requester_id"],
            organization_id=action["organization_id"],
            attempts=claimed["attempts"],
        )

    # ---------------------------------------------------------------------------------------
    def verify(self, job: ClaimedJob) -> str:
        """Run every pre-execution check. Returns the idempotency key, or raises."""
        if job.state not in ("APPROVED", "QUEUED", "EXECUTING"):
            raise RefusedToExecute(f"action_state_forbids_execution:{job.state}")

        with self._conn.cursor() as cur:
            cur.execute(_LOAD_DECISION, (job.action_request_id,))
            decision = cur.fetchone()
        self._conn.commit()

        if decision is None:
            raise RefusedToExecute("no_approval_decision")
        if decision["decision"] != "approved":
            raise RefusedToExecute(f"action_was_{decision['decision']}")
        if decision["approver_id"] == job.requester_id:
            # Belt and braces behind the policy rule and the database trigger.
            raise RefusedToExecute("self_approval_detected")
        if job.expires_at < datetime.now(UTC):
            raise RefusedToExecute("approval_expired")

        # The integrity check. The approver approved a hash; the payload about to execute must
        # still produce it, and it must match what the approval recorded.
        recomputed = payload_hash(job.payload)
        if recomputed != job.payload_hash:
            raise RefusedToExecute("payload_hash_mismatch_stored")
        if decision["approved_hash"] != job.payload_hash:
            raise RefusedToExecute("payload_hash_mismatch_approved")

        return idempotency_key(job.action_request_id, job.payload_hash)

    # ---------------------------------------------------------------------------------------
    def execute(self, job: ClaimedJob, key: str) -> Outcome:
        """Reserve the key, call the provider once, and record what happened.

        The reservation is inserted *before* the provider call. If this worker dies mid-call, the
        row is already there, so a later attempt sees the key is taken and reconciles rather than
        calling again.
        """
        with self._conn.cursor() as cur:
            try:
                cur.execute(
                    _RESERVE_IDEMPOTENCY,
                    {"job_id": job.job_id, "key": key, "provider": self._adapter.name},
                )
                self._conn.commit()
            except psycopg.errors.UniqueViolation:
                self._conn.rollback()
                # Someone already reserved this key. Do not call the provider; find out what
                # happened instead.
                return self._reconcile(job, key)

        result = self._adapter.execute(idempotency_key=key, payload=job.payload)

        if result.outcome is Outcome.AMBIGUOUS:
            logger.warning(
                "provider_ambiguous", extra={"job": job.job_id, "action": job.action_request_id}
            )
            return self._reconcile(job, key)

        self._record_outcome(job, key, result.outcome, result.provider_reference, result.detail)
        return result.outcome

    def _reconcile(self, job: ClaimedJob, key: str) -> Outcome:
        """Ask the provider what actually happened before deciding anything.

        This is the rule from SP-ARCH-001 §10: after an ambiguous timeout the worker checks provider
        state rather than retrying an operation that may already have completed.
        """
        observed = self._adapter.lookup(idempotency_key=key)

        if observed is None:
            # The provider has no record: the effect did not land. Safe to let the job retry.
            self._record_outcome(job, key, Outcome.FAILED, None, "reconciled: provider has no record")
            return Outcome.FAILED

        logger.info(
            "reconciled", extra={"job": job.job_id, "outcome": str(observed.outcome)}
        )
        self._record_outcome(
            job, key, observed.outcome, observed.provider_reference, "reconciled with provider"
        )
        return observed.outcome

    def _record_outcome(
        self,
        job: ClaimedJob,
        key: str,
        outcome: Outcome,
        reference: str | None,
        detail: str | None,
    ) -> None:
        """Write the execution result, the job state, the action state, and the audit event.

        One transaction: an execution that succeeded must never be visible without the evidence
        that says so.
        """
        succeeded = outcome is Outcome.SUCCEEDED
        retryable = outcome is Outcome.FAILED and job.attempts < 3

        job_state = "SUCCEEDED" if succeeded else ("QUEUED" if retryable else "FAILED")
        action_state = "SUCCEEDED" if succeeded else ("EXECUTING" if retryable else "FAILED")

        with self._conn.cursor() as cur:
            cur.execute(
                _COMPLETE_EXECUTION,
                {
                    "outcome": str(outcome),
                    "reference": reference,
                    "detail": detail,
                    "key": key,
                },
            )
            cur.execute(
                _FINISH_JOB,
                {
                    "job_id": job.job_id,
                    "state": job_state,
                    "error": None if succeeded else detail,
                    # Exponential backoff, so a provider having a bad minute is not hammered.
                    "backoff": 30 * (2 ** job.attempts),
                },
            )
            cur.execute(_SET_ACTION_STATE, {"id": job.action_request_id, "state": action_state})
            cur.execute(
                _AUDIT,
                {
                    "request_id": f"worker-{job.job_id}",
                    "actor_id": self._worker_id,
                    "organization_id": job.organization_id,
                    "action": f"{job.action_type}.execute",
                    "resource_id": job.action_request_id,
                    "decision": "succeeded" if succeeded else "failed",
                    "reason": detail or str(outcome),
                    "payload_hash": job.payload_hash,
                    "reference": reference,
                },
            )
        self._conn.commit()

    def refuse(self, job: ClaimedJob, reason: str) -> None:
        """Record a refusal without touching the provider."""
        with self._conn.cursor() as cur:
            cur.execute(
                _FINISH_JOB,
                {"job_id": job.job_id, "state": "FAILED", "error": reason, "backoff": 0},
            )
            cur.execute(_SET_ACTION_STATE, {"id": job.action_request_id, "state": "FAILED"})
            cur.execute(
                _AUDIT,
                {
                    "request_id": f"worker-{job.job_id}",
                    "actor_id": self._worker_id,
                    "organization_id": job.organization_id,
                    "action": f"{job.action_type}.execute",
                    "resource_id": job.action_request_id,
                    "decision": "failed",
                    "reason": reason,
                    "payload_hash": job.payload_hash,
                    "reference": None,
                },
            )
        self._conn.commit()
        logger.warning("execution_refused", extra={"job": job.job_id, "reason": reason})
