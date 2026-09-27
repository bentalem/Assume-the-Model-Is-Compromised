"""The mutation registry — everything the Range can do to the lab.

The browser sends an id. It never sends SQL, a role, a table, a container name or a file path, and
there is no endpoint that accepts any of those. What the Range can do is the list in this file, and
the list is short enough to read.

Four rules, and each one exists because of a specific way this kind of service goes wrong:

  **No mutation without an inverse.** A mutation registers only if it declares a restore. The
  failure this prevents is the worst one available here — a learner whose lab is quietly still
  armed an hour later, measuring a broken system and believing it is the real one.

  **The probe is the source of truth.** Armed or correct is read from the system on every render,
  never remembered from what the Range believes it did. A learner who arms something outside the
  Range, or restarts a container, sees the truth.

  **Reset asserts, it does not undo.** It walks every registered mutation, restores the ones whose
  probe is not `correct`, and reports what it changed. An undo log would be wrong the moment
  anything happened that the log did not record.

  **Observations are registry entries too.** Named, parameterless, with a fixed statement and a
  declared row cap. There is no query box in this product and there will not be one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import containers, db, memdb, memvectors, policy_bundle, probe, source

logger = logging.getLogger("supportpilot.range.registry")

ARMED = "armed"
CORRECT = "correct"
UNKNOWN = "unknown"
# The control belongs to a compose profile that is not running (track 9's memory stack). Not unknown —
# the Range can say exactly why it cannot read it — and never correct. Reset skips it: there is
# nothing running to restore.
ABSENT = "absent"


class RegistryError(Exception):
    """A registration that would let the Range do something it cannot undo or cannot see."""


@dataclass(frozen=True)
class Mutation:
    id: str
    summary: str
    apply: Callable[[], None]
    restore: Callable[[], None]
    probe: Callable[[], str]
    touches: tuple[str, ...] = ()
    # What the learner is told the armed state means, shown beside the switch.
    armed_means: str = ""


@dataclass(frozen=True)
class Observation:
    id: str
    summary: str
    run: Callable[[], list[dict[str, Any]]]
    columns: tuple[str, ...]
    row_cap: int
    # Named so a `value` flag can compare against a column of this result rather than a literal in
    # a content file: the answer lives in the seed data and the Range asks the database for it.
    fields: tuple[str, ...] = field(default=())


MUTATIONS: dict[str, Mutation] = {}
OBSERVATIONS: dict[str, Observation] = {}


def register_mutation(mutation: Mutation) -> None:
    if mutation.id in MUTATIONS:
        raise RegistryError(f"mutation id already registered: {mutation.id}")
    for name, fn in (("apply", mutation.apply), ("restore", mutation.restore), ("probe", mutation.probe)):
        if not callable(fn):
            raise RegistryError(f"{mutation.id}: {name} is not callable")
    MUTATIONS[mutation.id] = mutation


def register_observation(observation: Observation) -> None:
    if observation.id in OBSERVATIONS:
        raise RegistryError(f"observation id already registered: {observation.id}")
    if observation.row_cap <= 0:
        raise RegistryError(f"{observation.id}: an observation without a row cap is a bulk read")
    OBSERVATIONS[observation.id] = observation


# ==================================================================================================
# Track 2 · row security on app.orders
# ==================================================================================================

def _orders_flags() -> tuple[bool, bool] | None:
    row = db.table_security("orders")
    if row is None:
        return None
    return bool(row["rls_enabled"]), bool(row["rls_forced"])


def _probe_force() -> str:
    flags = _orders_flags()
    if flags is None:
        return UNKNOWN
    _, forced = flags
    return CORRECT if forced else ARMED


def _probe_enabled() -> str:
    flags = _orders_flags()
    if flags is None:
        return UNKNOWN
    enabled, _ = flags
    return CORRECT if enabled else ARMED


register_mutation(
    Mutation(
        id="rls.orders.force_off",
        summary="Drop FORCE from app.orders",
        apply=lambda: db.call("arm_orders_force_off"),
        restore=lambda: db.call("restore_orders_force"),
        probe=_probe_force,
        touches=("app.orders",),
        armed_means="The table's owner is exempt from its own policy. The policy is unchanged.",
    )
)

register_mutation(
    Mutation(
        id="rls.orders.disable",
        summary="Disable row security on app.orders",
        apply=lambda: db.call("arm_orders_rls_disable"),
        restore=lambda: db.call("restore_orders_rls"),
        probe=_probe_enabled,
        touches=("app.orders",),
        armed_means="Policies are not consulted at all. They still exist and are still correct.",
    )
)

register_observation(
    Observation(
        id="orders.as_owner",
        summary="SELECT from app.orders as the role that owns it, with a cedar tenant context",
        run=lambda: db.select("observe_orders_as_owner"),
        columns=("tenant", "order_number", "status", "currency", "total_amount"),
        row_cap=25,
        fields=("total_amount", "order_number"),
    )
)

register_observation(
    Observation(
        id="orders.catalogue",
        summary="Owner, enabled and forced for every table in app",
        run=db.all_table_security,
        columns=("table_name", "owner", "rls_enabled", "rls_forced"),
        row_cap=64,
    )
)

register_observation(
    Observation(
        id="roles.attributes",
        summary="Superuser and BYPASSRLS for every lab role",
        run=db.role_attributes,
        columns=("role_name", "is_superuser", "bypasses_rls"),
        row_cap=32,
    )
)


# ==================================================================================================
# Track 2 · the audit (2.3)
#
# The same shape of failure, moved to a table nobody is thinking about, with no hint about which.
# ==================================================================================================

def _probe_order_items_force() -> str:
    rows = db.select("table_security_order_items")
    if not rows:
        return UNKNOWN
    return CORRECT if rows[0]["rls_forced"] else ARMED


register_mutation(
    Mutation(
        id="rls.order_items.force_off",
        summary="Drop FORCE from app.order_items",
        apply=lambda: db.call("arm_order_items_force_off"),
        restore=lambda: db.call("restore_order_items_force"),
        probe=_probe_order_items_force,
        touches=("app.order_items",),
        armed_means="One table in sixteen is now exempt for its owner. The catalogue will say which.",
    )
)

register_observation(
    Observation(
        id="catalogue.unforced",
        summary="Tables that are not fully protected, and in which way",
        run=lambda: db.select("catalogue_unforced"),
        columns=("table_name", "owner", "rls_enabled", "rls_forced", "problem"),
        row_cap=64,
        fields=("table_name",),
    )
)


# ==================================================================================================
# Operations
# ==================================================================================================

def state() -> dict[str, str]:
    """Probe every mutation. Read from the system, every time, never cached."""
    out: dict[str, str] = {}
    for mutation_id, mutation in MUTATIONS.items():
        try:
            out[mutation_id] = mutation.probe()
        except Exception:  # noqa: BLE001 — an unreadable probe is `unknown`, never `correct`
            logger.exception("probe failed for %s", mutation_id)
            out[mutation_id] = UNKNOWN
    return out


def armed_count() -> int:
    return sum(1 for value in state().values() if value == ARMED)


def apply(mutation_id: str, request_id: str) -> str:
    """Arm one control, with evidence written before and after.

    The lab's rule is that a sensitive change and its audit row share a transaction, so that a
    failed write fails the change. This service cannot honour that literally: a mutation may stop a
    container or write a file, and no database transaction spans those. What it can do is never
    arm anything that is not already written down. The intent goes in first; if that write fails,
    nothing is armed. The outcome goes in after, so the pair is a record of what was attempted as
    well as what happened.

    Previously only the second write existed, and an arm followed by a failed record left a control
    armed with no evidence at all — in the service that teaches rule 9.
    """
    mutation = MUTATIONS.get(mutation_id)
    if mutation is None:
        raise KeyError(mutation_id)
    # 'allowed' rather than anything more descriptive: app.audit_events constrains decision to a
    # fixed vocabulary, and the intent row is exactly "this arm was permitted to proceed". Inventing
    # a value here would have failed the CHECK the first time a learner pressed Arm.
    db.record_event(request_id, "range.arm", mutation_id, "allowed", "arming_requested")
    try:
        mutation.apply()
    except Exception as exc:
        db.record_event(request_id, "range.arm", mutation_id, "failed", type(exc).__name__)
        raise
    db.record_event(request_id, "range.arm", mutation_id, "succeeded", "armed_by_learner")
    return mutation.probe()


def restore(mutation_id: str, request_id: str) -> str:
    mutation = MUTATIONS.get(mutation_id)
    if mutation is None:
        raise KeyError(mutation_id)
    mutation.restore()
    db.record_event(request_id, "range.restore", mutation_id, "succeeded", "restored_by_learner")
    return mutation.probe()


def reset(request_id: str) -> list[str]:
    """Assert the known-good configuration of every registered mutation.

    Returns the ids it actually had to change, which is what the learner is told. A reset that
    reports success without restoring is the failure this function exists to make impossible, so it
    re-probes afterwards and raises if anything is still armed.
    """
    # Probe everything before restoring anything. Four of these mutations write the same policy
    # bundle, so restoring the first also corrects the other three — and probing as we went credited
    # whichever was probed first. A learner who armed policy.bundle.conflict was told, in the console
    # and in the audit row, that policy.tenant_check.remove had been the thing restored.
    wrong: set[str] = set()
    for mutation_id, mutation in MUTATIONS.items():
        try:
            if mutation.probe() not in (CORRECT, ABSENT):
                wrong.add(mutation_id)
        except Exception:  # noqa: BLE001
            logger.exception("reset could not probe %s", mutation_id)
            wrong.add(mutation_id)

    changed: list[str] = []
    failed: list[str] = []
    for mutation_id, mutation in MUTATIONS.items():
        # One mutation must never end the sweep. The retry below used to sit outside any handler, so
        # a restore that raised twice — a stopped docker-proxy does exactly that — aborted the loop
        # partway through, and every mutation after it was neither probed nor restored, with no
        # report and no audit row. Whatever happens here, the remaining mutations still get their
        # turn and the post-check below still runs.
        if mutation_id not in wrong:
            continue
        changed.append(mutation_id)
        try:
            mutation.restore()
        except Exception:  # noqa: BLE001
            logger.exception("reset could not restore %s", mutation_id)
            failed.append(mutation_id)

    still_armed = sorted(
        {mid for mid, value in state().items() if value not in (CORRECT, ABSENT)} | set(failed)
    )
    db.record_event(
        request_id, "range.reset", ",".join(changed) or "none",
        "succeeded" if not still_armed else "failed",
        f"restored {len(changed)}" if not still_armed else f"still armed: {','.join(still_armed)}",
    )
    if still_armed:
        raise RuntimeError(f"reset did not restore: {', '.join(still_armed)}")
    return changed


def observe(observation_id: str) -> tuple[list[str], list[list[str]]]:
    """Run one registered observation and return (columns, rows) as display strings."""
    observation = OBSERVATIONS.get(observation_id)
    if observation is None:
        raise KeyError(observation_id)

    rows = observation.run()[: observation.row_cap]
    return (
        list(observation.columns),
        [[("" if row.get(column) is None else str(row.get(column))) for column in observation.columns]
         for row in rows],
    )


def observation_values(observation_id: str, field_name: str) -> list[str]:
    """Every value of one column, for checking a `value` flag against the database."""
    observation = OBSERVATIONS.get(observation_id)
    if observation is None:
        raise KeyError(observation_id)
    return [str(row.get(field_name)) for row in observation.run() if row.get(field_name) is not None]


# ==================================================================================================
# Track 7 · evidence
#
# Read-only. Nothing in this track arms anything: the subject is what the trail can and cannot show,
# and a challenge that broke something first would be answering a different question.
# ==================================================================================================

register_observation(
    Observation(
        id="audit.recent",
        summary="The last 30 decisions recorded by the API and the worker",
        run=lambda: db.select("recent_decisions"),
        columns=("at", "actor", "action", "resource", "decision", "reason", "policy_version"),
        row_cap=30,
        fields=("reason",),
    )
)

register_observation(
    Observation(
        id="audit.ord_3001",
        summary="Every recorded decision about ORD-3001",
        run=lambda: db.select_one_arg("decisions_for_resource", "ORD-3001"),
        columns=("at", "actor", "action", "decision", "reason", "policy_version"),
        row_cap=30,
        fields=("reason",),
    )
)

register_observation(
    Observation(
        id="audit.refund_chain",
        summary="Every recorded step of the most recently executed refund",
        run=lambda: db.select("reconstruct_last_refund"),
        columns=(
            "at", "request_id", "actor_type", "actor", "action", "resource",
            "decision", "reason", "policy_version", "payload_hash", "result_reference",
        ),
        row_cap=20,
        fields=("reason",),
    )
)

register_observation(
    Observation(
        id="audit.column_use",
        summary="How many audit rows actually carry each column",
        run=lambda: db.select("audit_column_use"),
        columns=("column_name", "populated", "total", "verdict"),
        row_cap=12,
    )
)

register_observation(
    Observation(
        id="audit.ord_2001",
        summary="Every recorded decision about ORD-2001",
        run=lambda: db.select_one_arg("decisions_for_resource", "ORD-2001"),
        columns=("at", "actor", "action", "decision", "reason", "policy_version"),
        row_cap=30,
        fields=("reason",),
    )
)


# ==================================================================================================
# Track 6 · separation of duty (6.2)
#
# These observations attempt a write. That is unusual here and deliberate: the subject of the
# challenge is what refuses the write, so a read could only describe it. Each attempt rolls itself
# back, and the permitted case is deleted by hand rather than left behind.
# ==================================================================================================

register_observation(
    Observation(
        id="actions.pending",
        summary="Action requests and their state, newest first",
        run=lambda: db.select("pending_actions"),
        columns=("action_id", "action_type", "resource", "state", "risk", "payload_hash"),
        row_cap=10,
    )
)

register_observation(
    Observation(
        id="approval.self_attempt",
        summary="Attempt to approve a request as the person who raised it",
        run=lambda: db.select("attempt_self_approval"),
        columns=("attempt", "outcome", "refused_by", "detail"),
        row_cap=1,
        fields=("refused_by", "outcome"),
    )
)

register_observation(
    Observation(
        id="approval.independent_attempt",
        summary="The same approval by a different person — the control group",
        run=lambda: db.select("attempt_independent_approval"),
        columns=("attempt", "outcome", "refused_by", "detail"),
        row_cap=1,
        fields=("refused_by", "outcome"),
    )
)


# ==================================================================================================
# Track 6 · payload binding (6.1)
# ==================================================================================================

def _probe_payload() -> str:
    rows = db.select("payload_binding")
    if not rows:
        return UNKNOWN
    return CORRECT if rows[0]["matches_proposal"].startswith("yes") else ARMED


register_mutation(
    Mutation(
        id="action.payload.tamper",
        summary="Change the amount on a pending refund, leaving the hash alone",
        apply=lambda: db.call("arm_tamper_payload"),
        restore=lambda: db.call("restore_payload"),
        probe=_probe_payload,
        touches=("app.action_requests",),
        armed_means="The payload says 4500.00. The hash still says what 45.00 hashed to.",
    )
)

register_observation(
    Observation(
        id="actions.payload_binding",
        summary="What each pending approval is bound to, and what its payload says now",
        run=lambda: db.select("payload_binding"),
        columns=("action_id", "state", "amount", "currency", "payload_hash", "approved_hash",
                 "matches_proposal"),
        row_cap=5,
        fields=("amount",),
    )
)


# ==================================================================================================
# Track 6 · approval expiry (6.4)
# ==================================================================================================

def _probe_window() -> str:
    rows = db.select("approval_window")
    if not rows:
        return UNKNOWN
    return CORRECT if rows[0]["window_status"] == "open" else ARMED


register_mutation(
    Mutation(
        id="action.approval.expire",
        summary="Move a pending request's approval window two hours into the past",
        apply=lambda: db.call("arm_expire_approval"),
        restore=lambda: db.call("restore_approval_window"),
        probe=_probe_window,
        touches=("app.action_requests",),
        armed_means="The request is still pending and its window has closed. Nothing else changed.",
    )
)

register_observation(
    Observation(
        id="actions.approval_window",
        summary="When the pending approval expires, against the server's own clock",
        run=lambda: db.select("approval_window"),
        columns=("action_id", "state", "expires_at", "server_now", "window_status", "minutes"),
        row_cap=1,
        fields=("window_status",),
    )
)


# ==================================================================================================
# Track 6 · exactly once (6.3)
# ==================================================================================================

register_observation(
    Observation(
        id="execution.evidence",
        summary="What has actually executed, and under which idempotency key",
        run=lambda: db.select("execution_evidence"),
        columns=("job", "idempotency_key", "provider", "outcome", "reference"),
        row_cap=10,
    )
)

register_observation(
    Observation(
        id="execution.replay_attempt",
        summary="Record the same effect a second time, under the same key",
        run=lambda: db.select("attempt_duplicate_effect"),
        columns=("attempt", "outcome", "refused_by", "detail"),
        row_cap=1,
        fields=("refused_by",),
    )
)

register_observation(
    Observation(
        id="execution.new_key_attempt",
        summary="The same insert under a fresh key — the control group",
        run=lambda: db.select("attempt_new_effect"),
        columns=("attempt", "outcome", "refused_by", "detail"),
        row_cap=1,
        fields=("refused_by",),
    )
)


# ==================================================================================================
# Track 6 · what the worker refuses, and why (6.1, 6.4)
#
# Every other observation in this track reports the lab's *state*: what the payload says now, when
# the window closes, what has executed. None of them can say what the worker would do about it,
# because the worker is a separate process with its own database role and the Range has no route to
# it — and 0018 explains at length why the Range does not reimplement the worker's canonicalisation
# in SQL to find out. That still holds. Nothing below recomputes a hash or evaluates a condition.
#
# What it does is read the worker's own pre-execution checks out of the worker's own source, in the
# order they run, and put the vocabulary on the page. Read rather than listed here, for the reason
# `tools.surface` reads the action document rather than a copy: a hand-maintained list in this file
# would drift from the code it claims to describe, and the drift would be invisible — which is the
# failure track 7 spends a whole challenge on.
#
# It reports the checks in `verify()` and nothing else. `claim()` and the worker's main loop can
# also refuse, but those are not pre-execution checks on an approved payload, and a list that mixed
# them in would answer a question the challenge did not ask.
# ==================================================================================================

_WORKER_PROCESSOR = "services/worker/src/supportpilot_worker/jobs/processor.py"


def _worker_refusals() -> list[dict[str, Any]]:
    """Every reason `JobProcessor.verify()` can refuse, in the order it checks them."""
    import re as _re

    path = source.REPO_ROOT / _WORKER_PROCESSOR
    if not path.is_file():
        return [{"order": "-", "refuses_when": "(the worker's source is not mounted)",
                 "reason_code": "-", "line": "-"}]

    lines = path.read_text(encoding="utf-8").splitlines()

    # The bounds of verify(), found by its definition and the next method at the same indentation.
    # Scanning the whole file would pick up claim()'s refusal as well, which is about a missing
    # row rather than about a payload somebody changed.
    start = end = None
    for number, line in enumerate(lines):
        if start is None:
            if _re.match(r"^    def verify\(", line):
                start = number
        elif _re.match(r"^    def \w", line):
            end = number
            break
    if start is None:
        return [{"order": "-", "refuses_when": "(verify() is not in this build of the worker)",
                 "reason_code": "-", "line": "-"}]
    if end is None:
        end = len(lines)

    raised = _re.compile(r'RefusedToExecute\(\s*f?"(.*?)"\s*\)')
    interpolation = _re.compile(r"\{[^}]*\}")

    def _named(expression: str) -> str:
        """`{job.state}` as `<state>`. The code is a template; the column should say so."""
        words = _re.sub(r"[^A-Za-z_]+", " ", expression).split()
        return f"<{words[-1] if words else '...'}>"

    rows: list[dict[str, Any]] = []
    condition = "-"
    for number in range(start, end):
        stripped = lines[number].strip()
        if stripped.startswith(("if ", "elif ")):
            condition = stripped.split(" ", 1)[1].rstrip(":")
        found = raised.search(stripped)
        if found:
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "refuses_when": condition,
                    "reason_code": interpolation.sub(
                        lambda match: _named(match.group(0)[1:-1]), found.group(1)
                    ),
                    "line": str(number + 1),
                }
            )
            condition = "-"

    if not rows:
        return [{"order": "-", "refuses_when": "(verify() raises nothing in this build)",
                 "reason_code": "-", "line": "-"}]
    return rows


register_observation(
    Observation(
        id="worker.refusals",
        summary="Every reason the worker can refuse to execute, in the order it checks them",
        run=_worker_refusals,
        columns=("order", "refuses_when", "reason_code", "line"),
        row_cap=12,
        fields=("reason_code",),
    )
)


# ==================================================================================================
# Track 7 · is the trail actually append-only (7.1)
#
# 7.1's Stage 03 makes a claim with two halves: no runtime role can amend a written row, and the
# owner can but changes nothing because FORCE row security applies the table's policies to it and
# there is no UPDATE policy for anyone. Both halves are statements about the catalogue, and the
# challenge that teaches "a schema is a promise, a query is evidence" should not be asking anyone
# to take them on the prose's word.
# ==================================================================================================

register_observation(
    Observation(
        id="audit.write_access",
        summary="Who may write to app.audit_events, per command, and which policy would match",
        run=lambda: db.select("audit_write_access"),
        columns=("command", "granted_to", "policies", "effect"),
        row_cap=8,
    )
)


# ==================================================================================================
# Requests made through the API, via the probe service
#
# The Range cannot reach the API. These ask `probe` for one of its registered requests, by id, over
# the control network. Two registries have to agree before anything happens, and neither service can
# extend the other's vocabulary — see docs/architecture/the-range.md.
#
# The result is the status, the error code and the *field names* in the response. Never values: a
# challenge that needs data reads it from the database through an observation above, where the row
# cap and the field list are already enforced.
# ==================================================================================================

_PROBE_COLUMNS = ("request", "as_user", "status", "error_code", "fields", "intent")


def _register_probe(observation_id: str, probe_id: str, summary: str) -> None:
    register_observation(
        Observation(
            id=observation_id,
            summary=summary,
            run=lambda: probe.run(probe_id),
            columns=_PROBE_COLUMNS,
            row_cap=1,
            fields=("error_code", "status", "fields"),
        )
    )


_register_probe("api.alice.own_order", "alice.read.own_order",
                "alice reads her own tenant's order — the control group")
_register_probe("api.alice.foreign_order", "alice.read.foreign_order",
                "alice reads an order belonging to the other tenant")
_register_probe("api.mallory.cedar_order", "mallory.read.cedar_order",
                "the same boundary from the other side")
_register_probe("api.alice.restricted_customer", "alice.read.restricted_customer",
                "a support agent reads a restricted customer")
_register_probe("api.bob.restricted_customer", "bob.read.restricted_customer",
                "a manager reads the same restricted customer")
_register_probe("api.fiona.order", "fiona.read.order",
                "an approver, who does not read orders, tries to")

# The one probe that carries a body, and the one whose result is meant to be boring: a refusal that
# happened before anything decided. 7.3 needs the learner to make this request themselves, because
# the finding is what it does *not* leave behind in the audit trail.
_register_probe("api.alice.invalid_refund", "alice.propose.invalid_reason",
                "alice proposes a refund with a reason outside the enumeration")


# ==================================================================================================
# Track 1 · roles come from the database (1.3)
# ==================================================================================================

def _probe_bob_manager() -> str:
    """Correct when somebody holds an active support_manager membership.

    The mutation demotes rather than revokes, so the armed state is the *absence* of the role — not
    a revoked row. Probing for a revoked row would have reported `correct` forever.
    """
    rows = db.select("memberships_for_lab_users")
    if not rows:
        return UNKNOWN
    active_managers = [r for r in rows if r["role"] == "support_manager" and r["status"] == "active"]
    return CORRECT if active_managers else ARMED


register_mutation(
    Mutation(
        id="identity.bob.revoke_manager",
        summary="Demote the manager to a support agent",
        apply=lambda: db.call("arm_revoke_bob_manager"),
        restore=lambda: db.call("restore_bob_manager"),
        probe=_probe_bob_manager,
        touches=("app.memberships",),
        armed_means="The membership now says support_agent. Every token already issued is unchanged.",
    )
)

register_observation(
    Observation(
        id="identity.memberships",
        summary="What the server believes about each person, which is what decides",
        run=lambda: db.select("memberships_for_lab_users"),
        columns=("person", "role", "status", "granted"),
        row_cap=16,
        fields=("status",),
    )
)


# ==================================================================================================
# Track 1 · tokens that are wrong in exactly one way (1.4)
# ==================================================================================================

def _register_tampered(observation_id: str, probe_id: str, summary: str) -> None:
    register_observation(
        Observation(
            id=observation_id,
            summary=summary,
            run=lambda: probe.run(probe_id, kind="tampered"),
            columns=_PROBE_COLUMNS,
            row_cap=1,
            fields=("error_code", "status"),
        )
    )


_register_tampered("token.unsigned", "alice.token.unsigned",
                   "alice's claims with alg=none and no signature")
_register_tampered("token.resigned", "alice.token.resigned",
                   "alice's claims re-signed with an attacker's key")
_register_tampered("token.claimed_org", "alice.token.claimed_org",
                   "a tenant claim rewritten, then re-signed")


# ==================================================================================================
# Track 5 · untrusted content (5.2)
# ==================================================================================================

_register_probe("api.alice.ticket_1001", "alice.read.tkt_1001",
                "alice reads the ticket carrying ten planted injections")

register_observation(
    Observation(
        id="content.injection_corpus",
        summary="The ten instruction-shaped messages in TKT-1001",
        run=lambda: db.select("injection_corpus"),
        columns=("n", "author", "visibility", "attempt"),
        row_cap=20,
    )
)

register_observation(
    Observation(
        id="content.registered_tools",
        summary="The tool modules the model can actually call",
        run=lambda: db.select("registered_tool_modules"),
        columns=("tool_module", "note"),
        row_cap=16,
    )
)


# ==================================================================================================
# Track 1 · a token for another service (1.2)
# ==================================================================================================

register_observation(
    Observation(
        id="token.other_service",
        summary="A valid, unexpired, correctly signed token minted for a different service",
        run=lambda: probe.run("alice.token.other_service", kind="audience"),
        columns=_PROBE_COLUMNS,
        row_cap=1,
        fields=("error_code", "status"),
    )
)


# ==================================================================================================
# Track 3 · deny by default (3.1)
#
# The only mutation that touches a container. It goes through the proxy allowlist, not the Docker
# socket — see containers.py for why that distinction is the whole design.
#
# The restore waits for the container to be running again before it returns. An asynchronous restore
# that returns early is a reset that reports success while the lab is still broken, which is the one
# failure the registry exists to prevent.
# ==================================================================================================

OPA_CONTAINER = "supportpilot-opa"


def _probe_opa() -> str:
    try:
        return CORRECT if containers.state(OPA_CONTAINER) == "running" else ARMED
    except containers.ContainerError:
        logger.exception("could not inspect %s", OPA_CONTAINER)
        return UNKNOWN


register_mutation(
    Mutation(
        id="policy.opa.stop",
        summary="Stop the policy decision point",
        apply=lambda: containers.stop(OPA_CONTAINER),
        restore=lambda: containers.start(OPA_CONTAINER),
        probe=_probe_opa,
        touches=("supportpilot-opa",),
        armed_means="There is no policy engine. Every authorization question now has no answer.",
    )
)

def _restart_opa() -> None:
    """OPA reads its bundle at startup and does not watch the directory."""
    containers.stop(OPA_CONTAINER)
    containers.start(OPA_CONTAINER)


def _arm_permissive_policy(variant: str) -> None:
    policy_bundle.arm(variant)
    _restart_opa()


def _restore_real_policy() -> None:
    policy_bundle.restore()
    _restart_opa()


register_mutation(
    Mutation(
        id="policy.tenant_check.remove",
        summary="Remove the tenant membership check from order.read in the live policy",
        apply=lambda: _arm_permissive_policy("tenant"),
        restore=_restore_real_policy,
        probe=lambda: policy_bundle.state("tenant"),
        touches=("supportpilot-opa",),
        armed_means=(
            "The policy now permits any support role to read an order in any tenant. Nothing "
            "changes: the API never asks it, because the resource load already refused."
        ),
    )
)

register_mutation(
    Mutation(
        id="policy.role_check.remove",
        summary="Remove the role check from order.read in the live policy",
        apply=lambda: _arm_permissive_policy("role"),
        restore=_restore_real_policy,
        probe=lambda: policy_bundle.state("role"),
        touches=("supportpilot-opa",),
        armed_means=(
            "Any member of a tenant can now read that tenant's orders, whatever their role. This "
            "one returns data, because nothing underneath the policy checks roles."
        ),
    )
)


register_mutation(
    Mutation(
        id="policy.bundle.conflict",
        summary="Add a rule that collides with the real one, so evaluation errors",
        apply=lambda: _arm_permissive_policy("conflict"),
        restore=_restore_real_policy,
        probe=lambda: policy_bundle.state("conflict"),
        touches=("supportpilot-opa",),
        armed_means=(
            "The bundle loads and cannot answer. Two arms are true with different values, which "
            "Rego refuses to resolve, so OPA returns 500 for every order.read."
        ),
    )
)

register_mutation(
    Mutation(
        id="policy.bundle.undefined",
        summary="Move the package, so the decision the API asks for does not exist",
        apply=lambda: _arm_permissive_policy("undefined"),
        restore=_restore_real_policy,
        probe=lambda: policy_bundle.state("undefined"),
        touches=("supportpilot-opa",),
        armed_means=(
            "OPA is healthy and answers 200 with no decision in it at all. An undefined policy is "
            "the quietest of the failure modes and the one most likely to be read as consent."
        ),
    )
)


register_observation(
    Observation(
        id="policy.bundle_state",
        summary="Which authorization policy OPA is loading, per way of changing it",
        run=lambda: [
            {"variant": name, "state": policy_bundle.state(name)}
            for name in (*policy_bundle.VARIANTS, *policy_bundle.BROKEN)
        ],
        columns=("variant", "state"),
        row_cap=4,
        fields=("state",),
    )
)


register_observation(
    Observation(
        id="policy.opa_state",
        summary="Whether the policy decision point is running, read from the container runtime",
        run=lambda: [{"container": OPA_CONTAINER, "state": _opa_state_text()}],
        columns=("container", "state"),
        row_cap=1,
        fields=("state",),
    )
)


def _opa_state_text() -> str:
    try:
        return containers.state(OPA_CONTAINER)
    except containers.ContainerError as exc:
        return f"unreadable: {exc}"


# ==================================================================================================
# Track 1 · whose token is it (1.1)
# ==================================================================================================

def _probe_service_account() -> str:
    """Correct when the service account holds no membership anywhere."""
    rows = db.select("service_account_reach")
    if not rows:
        return UNKNOWN
    return CORRECT if all(row["tenant"] is None for row in rows) else ARMED


register_mutation(
    Mutation(
        id="identity.service_account.grant",
        summary="Give the agent one credential with membership in every tenant",
        apply=lambda: db.call("arm_service_account"),
        restore=lambda: db.call("restore_service_account"),
        probe=_probe_service_account,
        touches=("app.memberships",),
        armed_means="One account is now a manager in both tenants. That breadth is the requirement.",
    )
)

register_observation(
    Observation(
        id="identity.service_account",
        summary="What the service account can reach, per tenant",
        run=lambda: db.select("service_account_reach"),
        columns=("account", "tenant", "role", "status"),
        row_cap=8,
    )
)

_register_probe("api.agent.cedar_order", "agent.read.cedar_order",
                "the service account reads cedar's order")
_register_probe("api.agent.northwind_order", "agent.read.northwind_order",
                "the same credential reads northwind's order")


# ==================================================================================================
# Track 4 · tool authority (4.1)
#
# Read from the published action document rather than from a list in this file. The point of the
# track is judging the surface a system actually exposes, and a hand-maintained copy of it would be
# the wrong thing to teach against — it would drift, and the drift would be invisible.
# ==================================================================================================

def _tool_descriptions() -> list[dict[str, Any]]:
    """The prose each operation carries, read from the published action document.

    `_tool_surface` shows an operation's shape. This shows its *text* — the summary a model is given
    to decide what the operation is for. Challenge 8.4 is about who is allowed to change that text
    and what records it, so the text has to be on the page rather than described.
    """
    import json as _json

    path = source.REPO_ROOT / "openapi" / "supportpilot-actions.json"
    if not path.is_file():
        return [{"operation": "(the action document is not mounted)", "summary": "-",
                 "reviewed_by": "-", "recorded_in": "-"}]

    document = _json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for _route, operations in sorted(document.get("paths", {}).items()):
        for _method, operation in sorted(operations.items()):
            summary = operation.get("summary") or "(none)"
            rows.append(
                {
                    "operation": operation.get("operationId", "?"),
                    "summary": summary if len(summary) <= 64 else summary[:61] + "...",
                    # Deliberately constant. Nothing in this system records either, and a column
                    # that said "-" would read as missing data rather than as the finding.
                    "reviewed_by": "nobody",
                    "recorded_in": "nothing",
                }
            )
    return rows


def _tool_surface() -> list[dict[str, Any]]:
    import json as _json

    path = source.REPO_ROOT / "openapi" / "supportpilot-actions.json"
    if not path.is_file():
        return [{"operation": "(the action document is not mounted)", "method": "-",
                 "path": "-", "parameters": "-", "body": "-"}]

    document = _json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for route, operations in sorted(document.get("paths", {}).items()):
        for method, operation in sorted(operations.items()):
            params = [
                f"{p['name']}:{p.get('schema', {}).get('type', '?')}"
                for p in operation.get("parameters", [])
            ]
            body = "-"
            request_body = operation.get("requestBody")
            if request_body:
                schema = request_body.get("content", {}).get("application/json", {}).get("schema", {})
                ref = schema.get("$ref", "")
                body = ref.rsplit("/", 1)[-1] if ref else "inline"
            rows.append(
                {
                    "operation": operation.get("operationId", "?"),
                    "method": method.upper(),
                    "path": route,
                    "parameters": ", ".join(params) or "-",
                    "body": body,
                }
            )
    return rows


register_observation(
    Observation(
        id="tools.descriptions",
        summary="The text each operation carries for a model to read, and what guards it",
        run=_tool_descriptions,
        columns=("operation", "summary", "reviewed_by", "recorded_in"),
        row_cap=32,
    )
)


register_observation(
    Observation(
        id="search.enumeration",
        summary="One two-character query, paged to exhaustion, counted",
        run=lambda: probe.enumerate_directory("alice.enumerate.customers"),
        columns=("calls", "distinct_records", "every_call_allowed", "more_pages_remaining", "intent"),
        row_cap=1,
        fields=("distinct_records",),
    )
)


register_observation(
    Observation(
        id="tools.surface",
        summary="Every registered operation, read from the published action document",
        run=_tool_surface,
        columns=("operation", "method", "path", "parameters", "body"),
        row_cap=32,
    )
)


# ==================================================================================================
# Track 9 · context, history and memory
#
# Eight settings in memory-db, each flipped by range_mem.set_setting and read by range_mem's
# setting_state — as separate calls, always: read in the statement that changed it, a setting still
# shows its old value.
#
# Three of them let something through that outlives the setting — a memory born confirmed (9.5), a
# rule that activated itself (9.7), a summary that survived a forget (9.8). For those the probe asks
# about the leftovers too, and the restore removes them: restoring a switch closes the hole and does
# nothing about what already came through it, and a probe that reported `correct` over the leftovers
# would be reporting the switch rather than the system.
#
# The flag observations run their scenario first, through the probe service, and then read what the
# service logged. So each one is a measurement of the system as it is now: arm a control, run the
# observation, and the value appears; restore it, run it again, and it does not.
# ==================================================================================================

MEMORY_INIT_CONTAINER = "supportpilot-memory-init"


def _memory_probe(key: str, leftover: str | None = None) -> Callable[[], str]:
    def probe_fn() -> str:
        try:
            setting = memdb.setting_state(key)
            remaining = memdb.leftovers().get(leftover, 0) if leftover else 0
        except memdb.MemoryStackNotRunning:
            return ABSENT
        if setting == "armed" or (setting == "correct" and remaining > 0):
            return ARMED
        return CORRECT if setting == "correct" else UNKNOWN

    return probe_fn


def _restore_forget_scope() -> None:
    memdb.set_setting("forget.scope", "all")
    # The repair: memory-init completes every forget left half done and removes the points of
    # forgotten records — only now that the setting says forgetting is complete.
    containers.run_to_completion(MEMORY_INIT_CONTAINER)


def _restore_auto_confirm() -> None:
    memdb.set_setting("write.auto_confirm", "false")
    memdb.scalar("revoke_auto_confirmations")


def _restore_self_activate() -> None:
    memdb.set_setting("rules.self_activate", "false")
    memdb.scalar("retire_unapproved_rules")


_MEMORY_MUTATIONS = (
    ("memory.write.secret_filter_off", "write.secret_filter", "on", "off", None, None,
     "Stop redacting credentials from what memory stores",
     "History and memory keep a credential exactly as a tool returned it. Nothing else changes."),
    ("memory.context.provenance_off", "context.provenance", "on", "off", None, None,
     "Stop labelling where each line of context came from",
     "The context block is the same content with the labels removed. The model cannot tell a "
     "tool's output from the user's words — and could not reliably before, either."),
    ("memory.history.org_readable", "history.org_readable", "false", "true", None, None,
     "Let managers read colleagues' conversations with the agent",
     "A support manager may read any session in their organisation. Only managers, only their "
     "own organisation, and only to read."),
    ("memory.history.revalidate_off", "history.revalidate", "on", "off", None, None,
     "Replay history without checking the caller's current role",
     "A tool turn produced under a role the caller has since lost is included anyway. Nothing is "
     "wrong with the turn itself."),
    ("memory.write.auto_confirm", "write.auto_confirm", "false", "true",
     "auto_confirmed_memories", _restore_auto_confirm,
     "Let the agent's own memories count without the user confirming them",
     "What the model decides to remember is used from the next turn on. Restoring it also sends "
     "every memory confirmed this way back to wait for its owner."),
    ("memory.store.shared_collection", "store.layout", "per_tenant", "shared", None, None,
     "Serve long-term memory from one collection shared by every tenant",
     "Every tenant's vectors in one collection, separated by a filter on each query. The data was "
     "already there — the service writes both layouts — so only the query changes."),
    ("memory.rules.self_activate", "rules.self_activate", "false", "true",
     "rules_active_without_approval", _restore_self_activate,
     "Let a rule the agent proposes take effect immediately",
     "A proposal is born active: nobody approves it. Restoring it also retires every rule that "
     "became active that way."),
    ("memory.forget.primary_only", "forget.scope", "all", "primary",
     "derivations_of_forgotten_memories", _restore_forget_scope,
     "Forget only the record itself, not its summaries or vectors",
     "Forget deletes the one row. Its summaries stay live and its vectors stay in both layouts. "
     "Restoring it re-runs memory-init, which completes what was left half done."),
)

for (_id, _key, _secure, _armed, _leftover, _restore, _summary, _means) in _MEMORY_MUTATIONS:
    register_mutation(
        Mutation(
            id=_id,
            summary=_summary,
            apply=(lambda key=_key, value=_armed: memdb.set_setting(key, value)),
            restore=(_restore or (lambda key=_key, value=_secure: memdb.set_setting(key, value))),
            probe=_memory_probe(_key, _leftover),
            touches=(f"mem.settings[{_key}]",),
            armed_means=_means,
        )
    )


# --------------------------------------------------------------------------------------------------
# Scenario panels: the steps a scenario made, as status, error code and field names.
# --------------------------------------------------------------------------------------------------

_SCENARIO_COLUMNS = ("step", "as_user", "request", "status", "error_code", "fields")


def _register_scenario(observation_id: str, scenario_id: str, summary: str) -> None:
    register_observation(
        Observation(
            id=observation_id,
            summary=summary,
            run=lambda: probe.run_scenario(scenario_id),
            columns=_SCENARIO_COLUMNS,
            row_cap=6,
            fields=("status", "error_code"),
        )
    )


_register_scenario("memory.alice.confirm_latest", "memory.alice.confirm_latest",
                   "alice confirms the most recent memory waiting for her — the secure path")
_register_scenario("memory.mallory.recall", "memory.mallory.recall",
                   "mallory recalls northwind's own memory — the control group")
_register_scenario("memory.fiona.approve_latest_rule", "memory.fiona.approve_latest_rule",
                   "fiona approves the most recent proposal, by the hash of its text")
_register_scenario("memory.fiona.retire_latest_rule", "memory.fiona.retire_latest_rule",
                   "fiona retires the most recently activated rule")


# --------------------------------------------------------------------------------------------------
# Composite observations: run a scenario, then read what the memory service logged.
# --------------------------------------------------------------------------------------------------

Rows = list[dict[str, Any]]


def _after(scenario_id: str, read: Callable[[], Rows]) -> Callable[[], Rows]:
    def run() -> list[dict[str, Any]]:
        probe.run_scenario(scenario_id)
        return read()

    return run


_CONTEXT_BASE = ("item_no", "kind", "source", "included", "content")

register_observation(
    Observation(
        id="memory.context.after_tool_result",
        summary="The runtime stores a tool result for alice, builds her next context, and this "
                "shows the block the service logged",
        run=_after("memory.alice.runtime_store_tool_turn",
                   lambda: memdb.select("latest_context", "alice")),
        columns=_CONTEXT_BASE + ("secret_shaped",),
        row_cap=30,
        fields=("secret_shaped",),
    )
)

register_observation(
    Observation(
        id="memory.context.alice_lines",
        summary="The runtime builds alice's context for TKT-1001; this is the block as the model "
                "reads it, line by line",
        run=_after("memory.alice.context", lambda: memdb.select("latest_context_lines", "alice")),
        columns=("line_no", "line"),
        row_cap=40,
    )
)

register_observation(
    Observation(
        id="memory.context.alice_items",
        summary="alice's most recent context block, item by item, with where each came from",
        run=lambda: memdb.select("latest_context", "alice"),
        columns=_CONTEXT_BASE + ("confirmed_by_nobody",),
        row_cap=30,
    )
)

register_observation(
    Observation(
        id="memory.transcript.bob_reads_alice",
        summary="bob asks to read alice's session about TKT-1002; this shows what the service "
                "decided and, only if it allowed it, what bob received",
        run=_after("memory.bob.read_alice_transcript",
                   lambda: memdb.select("bob_reads_alice_transcript")),
        columns=("attempted_at", "decision", "reason", "seq", "role", "content", "marker"),
        row_cap=20,
        fields=("marker",),
    )
)

register_observation(
    Observation(
        id="memory.context.bob_escalation",
        summary="bob looks up CUS-4003 through the API, the runtime records the result, and bob's "
                "context for the escalation is rebuilt",
        run=_after("memory.bob.runtime_record_customer",
                   lambda: memdb.select("latest_context", "bob")),
        columns=("item_no", "kind", "source", "produced_under", "roles_now", "included", "content",
                 "outlived_email"),
        row_cap=30,
        fields=("outlived_email",),
    )
)

register_observation(
    Observation(
        id="memory.context.after_ticket_note",
        summary="The model stores TKT-1001's internal note as alice's memory, then her context is "
                "rebuilt",
        run=_after("memory.alice.remember_ticket_note",
                   lambda: memdb.select("latest_context", "alice")),
        columns=_CONTEXT_BASE + ("confirmed_by_nobody",),
        row_cap=30,
        fields=("confirmed_by_nobody",),
    )
)

register_observation(
    Observation(
        id="memory.records.alice",
        summary="alice's most recent memories: who wrote each, and who confirmed it",
        run=lambda: memdb.select("records_of", "alice"),
        columns=("created_at", "record_id", "channel", "status", "confirmed_via", "content"),
        row_cap=10,
    )
)

register_observation(
    Observation(
        id="memory.rules.after_proposal",
        summary="The model proposes a refund rule for cedar; these are cedar's rules afterwards",
        run=_after("memory.alice.propose_rule", lambda: memdb.select("rule_states")),
        columns=("created_at", "rule_id", "state", "proposed_by", "channel", "decided_by",
                 "retired_by", "rule_text", "active_without_approval"),
        row_cap=12,
        fields=("active_without_approval",),
    )
)

register_observation(
    Observation(
        id="memory.rules.states",
        summary="cedar's rules, newest first, and who decided each",
        run=lambda: memdb.select("rule_states"),
        columns=("created_at", "rule_id", "state", "proposed_by", "channel", "decided_by",
                 "retired_by", "rule_text"),
        row_cap=12,
    )
)


# 9.6 — the store, queried the way the service queries it, minus the filter.

_MARKER = re.compile(r"[A-Z]{3,}-[A-Z]{3,}-[0-9]{2,}")


def _store_without_filter() -> list[dict[str, Any]]:
    """What the service's own credential returns for cedar when the query carries no filter.

    Per-tenant: the service reads cedar from cedar's collection, with a token that names only that
    collection — and the same token asked for northwind's collection is refused by Qdrant. Shared:
    the service reads cedar from the collection every tenant is in, and the only thing between cedar
    and northwind was the filter this query leaves out.
    """
    layout = memdb.get_setting("store.layout")
    rows: list[dict[str, Any]] = []

    def add(collection: str, token_name: str, credential: str) -> None:
        status, points = memvectors.scroll_unfiltered(collection, token_name)
        if status != 200:
            rows.append({"layout": layout, "collection": collection, "credential": credential,
                         "status": str(status), "org": "-", "owner": "-",
                         "content": "refused by the vector store", "marker": None})
            return
        for point in points:
            payload = point.get("payload") or {}
            content = str(payload.get("content", ""))
            found = _MARKER.search(content)
            rows.append({"layout": layout, "collection": collection, "credential": credential,
                         "status": "200", "org": payload.get("org_id", ""),
                         "owner": payload.get("owner_sub", ""), "content": content[:160],
                         "marker": found.group(0) if found else None})

    if layout == "shared":
        add("memories__shared", "range_qdrant_shared_ro", "the service's shared-collection token")
    else:
        add("memories__cedar", "range_qdrant_cedar_ro", "cedar's collection token")
        add("memories__northwind", "range_qdrant_cedar_ro", "cedar's collection token")
    return rows


register_observation(
    Observation(
        id="memory.store.without_the_filter",
        summary="The vector store queried as the service queries it for cedar — with the filter left "
                "out",
        run=_store_without_filter,
        columns=("layout", "collection", "credential", "status", "org", "owner", "content",
                 "marker"),
        row_cap=30,
        fields=("marker",),
    )
)


# 9.8 — where a forgotten memory still lives.

def _remaining_copies() -> list[dict[str, Any]]:
    probe.run_scenario("memory.alice.forget_scenario")
    rows: list[dict[str, Any]] = []
    for record in memdb.select("remaining_copies"):
        record_id = str(record["record_id"])
        rows.append({"where": "memory-db", "record_id": record_id,
                     "relation": record["relation"], "state": record["state"],
                     "content": record["content"], "survivor": record["survivor"]})
        for collection in ("memories__cedar", "memories__shared"):
            status, payload = memvectors.point_present(collection, record_id)
            present = status == 200
            rows.append({"where": f"qdrant {collection}", "record_id": record_id,
                         "relation": record["relation"],
                         "state": "point present" if present else f"no point ({status})",
                         "content": str((payload or {}).get("content", ""))[:160],
                         # A point for a forgotten record is a copy that outlived the forget.
                         "survivor": record_id if present and record["state"] == "forgotten"
                         else None})
    return rows


register_observation(
    Observation(
        id="memory.forget.remaining_copies",
        summary="alice stores, confirms and summarises a memory, then forgets it; this is every "
                "place its content still lives",
        run=_remaining_copies,
        columns=("where", "record_id", "relation", "state", "content", "survivor"),
        row_cap=30,
        fields=("survivor",),
    )
)

register_observation(
    Observation(
        id="memory.outbox",
        summary="Changes written to memory-db and not yet applied to the vector store",
        run=lambda: memdb.select("outbox_state"),
        columns=("op", "pending", "oldest"),
        row_cap=4,
    )
)
