"""The action state machine and payload integrity.

Two ideas, both from SP-ARCH-001 §7:

* **State transitions are explicit and one-way.** The allowed set below is the whole map; anything
  not in it is not a transition. The database CHECK constrains which values may exist, and the row
  policies constrain who may write which — this module is the third layer, so an illegal move is
  caught before it reaches either.

* **Approval binds to a hash, not to a row.** The payload is canonicalised and hashed at proposal
  time. The approver approves that hash; the worker recomputes it before executing. Any change to
  amount, currency, destination, or resource produces a different hash and invalidates the
  approval, without anyone having to remember to re-check each field.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any


class ActionState(StrEnum):
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


#: Who may cause each transition. Named so a violation reads as a sentence in the audit trail.
ALLOWED_TRANSITIONS: dict[ActionState, frozenset[ActionState]] = {
    ActionState.PROPOSED: frozenset({ActionState.PENDING_APPROVAL, ActionState.CANCELLED}),
    ActionState.PENDING_APPROVAL: frozenset(
        {ActionState.APPROVED, ActionState.REJECTED, ActionState.CANCELLED}
    ),
    ActionState.APPROVED: frozenset({ActionState.QUEUED, ActionState.CANCELLED}),
    ActionState.QUEUED: frozenset({ActionState.EXECUTING, ActionState.CANCELLED}),
    ActionState.EXECUTING: frozenset(
        {ActionState.SUCCEEDED, ActionState.FAILED, ActionState.QUEUED}
    ),
    # Terminal. Nothing leaves these — a correction is a *new* action, never an edit of an old one
    # (SP-OPS-001 §6, "Manual correction or compensation requires a new controlled action").
    ActionState.SUCCEEDED: frozenset(),
    ActionState.FAILED: frozenset(),
    ActionState.REJECTED: frozenset(),
    ActionState.CANCELLED: frozenset(),
}

TERMINAL_STATES = frozenset(
    {ActionState.SUCCEEDED, ActionState.FAILED, ActionState.REJECTED, ActionState.CANCELLED}
)


class IllegalTransition(Exception):
    """An attempt to move an action along a path that does not exist."""

    def __init__(self, current: ActionState, requested: ActionState) -> None:
        super().__init__(f"{current} -> {requested} is not an allowed transition")
        self.current = current
        self.requested = requested


def assert_transition(current: ActionState | str, requested: ActionState | str) -> None:
    """Raise unless the move is on the map."""
    current_state = ActionState(current)
    requested_state = ActionState(requested)
    if requested_state not in ALLOWED_TRANSITIONS[current_state]:
        raise IllegalTransition(current_state, requested_state)


def can_transition(current: ActionState | str, requested: ActionState | str) -> bool:
    try:
        assert_transition(current, requested)
        return True
    except (IllegalTransition, ValueError):
        return False


def canonical_payload(payload: dict[str, Any]) -> str:
    """Render a payload to its one canonical form.

    Sorted keys, no insignificant whitespace, UTF-8. Two payloads that mean the same thing must
    hash the same, and two that differ in any value must not — so key order and spacing cannot be
    used to slip a changed amount past an approval.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    """The value an approval binds to."""
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def hashes_match(expected: str, payload: dict[str, Any]) -> bool:
    """Constant-time comparison of a stored hash against a freshly computed one."""
    import hmac

    return hmac.compare_digest(expected, payload_hash(payload))


def idempotency_key(action_id: str, hash_value: str) -> str:
    """The key that makes execution happen at most once.

    Derived from the action and the exact approved payload, so a retry of the same approved action
    reuses it and the unique constraint absorbs the duplicate. A changed payload produces a
    different key — but it also fails the hash check long before it reaches the provider.
    """
    return f"{action_id}:{hash_value[:32]}"
