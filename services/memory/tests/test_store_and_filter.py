"""How request context reaches the store, and what the secret filter does."""

from __future__ import annotations

import psycopg
import pytest

from supportpilot_memory import secrets_filter
from supportpilot_memory.db import MemoryDatabase
from supportpilot_memory.errors import ApiError

from .conftest import ALICE_SUB, CEDAR, RecordingCursor

# ------------------------------------------------------------------------------------------------
# Request context. Transaction-local, bound, and empty — never missing — when there is no principal.
# ------------------------------------------------------------------------------------------------


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor

    def transaction(self):
        return _Tx()

    def cursor(self):
        cursor = self._cursor

        class _Ctx:
            def __enter__(self_inner):
                return cursor

            def __exit__(self_inner, *a):
                return False

        return _Ctx()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def connection(self, timeout=None):
        return self._conn


def _db(cursor):
    db = MemoryDatabase.__new__(MemoryDatabase)
    db._pool = _Pool(_Conn(cursor))
    return db


def test_context_is_set_transaction_locally_with_bound_values(alice):
    cursor = RecordingCursor()
    with _db(cursor).transaction(alice):
        pass
    query, params = cursor.executed[0]
    # `true` is is_local: SET LOCAL, never a session SET on a pooled connection (challenge 2.2).
    assert query.count(", true)") == 3
    assert "%s" in query and ALICE_SUB not in query
    assert params == (ALICE_SUB, CEDAR, "support_agent")


def test_no_principal_sets_empty_context_which_every_policy_reads_as_nothing():
    cursor = RecordingCursor()
    with _db(cursor).transaction(None):
        pass
    assert cursor.executed[0][1] == ("", "", "")


class _Failing(RecordingCursor):
    def __init__(self, error):
        super().__init__()
        self._error = error

    def execute(self, query, params=()):
        raise self._error


def test_an_unreachable_store_is_an_outage_not_an_answer(alice):
    with pytest.raises(ApiError) as exc:
        with _db(_Failing(psycopg.OperationalError("gone"))).transaction(alice):
            pass
    assert exc.value.status_code == 503


def test_a_row_policy_refusal_is_reported_as_a_refusal(alice):
    """The store said no. That must reach the caller as a decision, not be swallowed as an outage."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with _db(_Failing(psycopg.errors.InsufficientPrivilege("rls"))).transaction(alice):
            pass


# ------------------------------------------------------------------------------------------------
# The secret filter.
# ------------------------------------------------------------------------------------------------

EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"  # AWS's own documentation example — test data by design


def test_detects_a_credential_shaped_value():
    assert secrets_filter.contains_secret(f"the tool returned key {EXAMPLE_KEY} for you")


def test_does_not_flag_ordinary_text():
    assert not secrets_filter.contains_secret("order ORD-2001 shipped on Tuesday")


def test_redaction_removes_the_value_and_keeps_the_sentence():
    redacted = secrets_filter.redact(f"key is {EXAMPLE_KEY} ok")
    assert EXAMPLE_KEY not in redacted
    assert redacted.startswith("key is ") and redacted.endswith(" ok")


@pytest.mark.parametrize("stored, enabled", [
    ({"value": "on"}, True),
    ({"value": "off"}, False),
    # Deny by default: a missing or unexpected setting must not be what lets a secret in.
    (None, True),
    ({"value": "maybe"}, True),
])
def test_the_filter_is_on_unless_explicitly_off(stored, enabled):
    cursor = RecordingCursor({"mem.setting": stored})
    assert secrets_filter.filter_enabled(cursor) is enabled
