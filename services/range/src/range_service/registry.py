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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import db

logger = logging.getLogger("supportpilot.range.registry")

ARMED = "armed"
CORRECT = "correct"
UNKNOWN = "unknown"


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
    mutation = MUTATIONS.get(mutation_id)
    if mutation is None:
        raise KeyError(mutation_id)
    mutation.apply()
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
    changed: list[str] = []
    for mutation_id, mutation in MUTATIONS.items():
        try:
            if mutation.probe() != CORRECT:
                mutation.restore()
                changed.append(mutation_id)
        except Exception:  # noqa: BLE001
            logger.exception("reset failed for %s", mutation_id)
            mutation.restore()
            changed.append(mutation_id)

    still_armed = [mid for mid, value in state().items() if value != CORRECT]
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
