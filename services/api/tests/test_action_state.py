"""Phase 4 — the state machine and payload integrity.

These are the pure functions the whole approval chain rests on, so they get exhaustive tests rather
than representative ones: every state pair is checked, not a sample.
"""

from __future__ import annotations

import pytest

from supportpilot_api.actions.state import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    ActionState,
    IllegalTransition,
    assert_transition,
    can_transition,
    canonical_payload,
    hashes_match,
    idempotency_key,
    payload_hash,
)

PAYLOAD = {
    "action_type": "refund",
    "order_number": "ORD-2001",
    "organization_id": "11111111-1111-1111-1111-111111111111",
    "amount": "49.90",
    "currency": "USD",
    "reason": "damaged_on_arrival",
}


# --- the transition map --------------------------------------------------------------------------
def test_every_state_appears_in_the_map():
    """A state with no entry would raise KeyError at runtime instead of refusing a transition."""
    assert set(ALLOWED_TRANSITIONS) == set(ActionState)


def test_terminal_states_allow_nothing():
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset(), f"{state} is not terminal"


def test_the_happy_path_is_walkable():
    path = [
        ActionState.PROPOSED,
        ActionState.PENDING_APPROVAL,
        ActionState.APPROVED,
        ActionState.QUEUED,
        ActionState.EXECUTING,
        ActionState.SUCCEEDED,
    ]
    for current, following in zip(path[:-1], path[1:], strict=True):
        assert_transition(current, following)


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        # The shortcuts that must not exist: reaching execution without approval.
        (ActionState.PROPOSED, ActionState.APPROVED),
        (ActionState.PROPOSED, ActionState.QUEUED),
        (ActionState.PROPOSED, ActionState.EXECUTING),
        (ActionState.PROPOSED, ActionState.SUCCEEDED),
        (ActionState.PENDING_APPROVAL, ActionState.QUEUED),
        (ActionState.PENDING_APPROVAL, ActionState.EXECUTING),
        (ActionState.PENDING_APPROVAL, ActionState.SUCCEEDED),
        (ActionState.APPROVED, ActionState.SUCCEEDED),
        (ActionState.APPROVED, ActionState.EXECUTING),
        # Reviving something already decided.
        (ActionState.REJECTED, ActionState.APPROVED),
        (ActionState.REJECTED, ActionState.PENDING_APPROVAL),
        (ActionState.SUCCEEDED, ActionState.QUEUED),
        (ActionState.SUCCEEDED, ActionState.PENDING_APPROVAL),
        (ActionState.CANCELLED, ActionState.APPROVED),
        (ActionState.FAILED, ActionState.SUCCEEDED),
    ],
)
def test_forbidden_transitions_are_refused(current, requested):
    assert not can_transition(current, requested)
    with pytest.raises(IllegalTransition):
        assert_transition(current, requested)


def test_no_state_can_reach_succeeded_without_executing():
    """The only door into SUCCEEDED is EXECUTING, which itself requires an approval upstream."""
    doors = [s for s, targets in ALLOWED_TRANSITIONS.items() if ActionState.SUCCEEDED in targets]
    assert doors == [ActionState.EXECUTING]


def test_no_state_can_reach_approved_except_pending_approval():
    doors = [s for s, targets in ALLOWED_TRANSITIONS.items() if ActionState.APPROVED in targets]
    assert doors == [ActionState.PENDING_APPROVAL]


def test_unknown_state_names_are_rejected():
    assert not can_transition("PROPOSED", "TOTALLY_MADE_UP")
    assert not can_transition("NOT_A_STATE", "APPROVED")


# --- canonicalisation and hashing ----------------------------------------------------------------
def test_key_order_does_not_change_the_hash():
    reordered = dict(reversed(list(PAYLOAD.items())))
    assert payload_hash(PAYLOAD) == payload_hash(reordered)


def test_canonical_form_has_no_insignificant_whitespace():
    assert ", " not in canonical_payload(PAYLOAD)
    assert ": " not in canonical_payload(PAYLOAD)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", "49.91"),
        ("amount", "490.90"),
        ("currency", "EUR"),
        ("order_number", "ORD-2002"),
        ("organization_id", "22222222-2222-2222-2222-222222222222"),
        ("reason", "other"),
        ("action_type", "payout"),
    ],
)
def test_any_field_change_changes_the_hash(field, value):
    """This is what makes approval binding: nothing about the action can move silently."""
    tampered = dict(PAYLOAD, **{field: value})
    assert payload_hash(tampered) != payload_hash(PAYLOAD)


def test_adding_a_field_changes_the_hash():
    assert payload_hash({**PAYLOAD, "destination": "attacker"}) != payload_hash(PAYLOAD)


def test_removing_a_field_changes_the_hash():
    reduced = {k: v for k, v in PAYLOAD.items() if k != "currency"}
    assert payload_hash(reduced) != payload_hash(PAYLOAD)


def test_hash_is_a_sha256_hex_digest():
    digest = payload_hash(PAYLOAD)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_hashes_match_accepts_the_original_and_rejects_a_change():
    digest = payload_hash(PAYLOAD)
    assert hashes_match(digest, PAYLOAD)
    assert not hashes_match(digest, dict(PAYLOAD, amount="500.00"))


def test_hashes_match_rejects_a_malformed_stored_value():
    assert not hashes_match("", PAYLOAD)
    assert not hashes_match("a" * 64, PAYLOAD)


def test_unicode_amounts_do_not_collide():
    """A full-width digit is a different string and must not hash to the ASCII one."""
    assert payload_hash(dict(PAYLOAD, amount="４９.９０")) != payload_hash(PAYLOAD)


# --- idempotency keys ----------------------------------------------------------------------------
def test_idempotency_key_is_stable_for_the_same_action_and_payload():
    digest = payload_hash(PAYLOAD)
    assert idempotency_key("a-1", digest) == idempotency_key("a-1", digest)


def test_idempotency_key_differs_across_actions():
    digest = payload_hash(PAYLOAD)
    assert idempotency_key("a-1", digest) != idempotency_key("a-2", digest)


def test_idempotency_key_differs_when_the_payload_differs():
    assert idempotency_key("a-1", payload_hash(PAYLOAD)) != idempotency_key(
        "a-1", payload_hash(dict(PAYLOAD, amount="1.00"))
    )
