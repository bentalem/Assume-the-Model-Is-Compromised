"""Phase 3 — the write path.

The property that matters most here cannot be seen from outside: business state and its evidence
must commit together. A note that exists without an audit row is exactly the situation
SP-ARCH-001 §10 forbids, and the only way to prove it is to make the audit write fail and check
that the note went with it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest

from supportpilot_api.repositories.notes import NoteRepository, StaleTicketError

from .conftest import ALICE_UUID, CEDAR


class FakeCursor:
    """A cursor that records statements and can be told to fail on the audit insert."""

    def __init__(self, *, insert_returns: dict | None, fail_on_audit: bool = False) -> None:
        self.statements: list[str] = []
        self._insert_returns = insert_returns
        self._fail_on_audit = fail_on_audit
        self._last: dict | None = None

    def execute(self, statement: str, params=None):
        self.statements.append(statement)
        if "app.audit_events" in statement:
            if self._fail_on_audit:
                raise psycopg.errors.CheckViolation("audit write failed")
            self._last = None
            return
        if "app.internal_notes" in statement:
            self._last = self._insert_returns
            return
        self._last = None

    def fetchone(self):
        return self._last


class FakeTransaction:
    """Stands in for Database.transaction, tracking whether the block completed."""

    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.context: dict = {}

    def __call__(self, **kwargs):
        self.context = kwargs
        return self

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class RealAuditWriter:
    """The real writer's record_in, which deliberately lets failures propagate."""

    def record_in(self, cursor, event):
        cursor.execute("INSERT INTO app.audit_events (...) VALUES (...)", event.as_params())


@pytest.fixture
def created_row():
    return {"id": "note-1", "created_at": datetime.now(UTC)}


def build(cursor: FakeCursor):
    transaction = FakeTransaction(cursor)

    class FakeDatabase:
        pass

    database = FakeDatabase()
    database.transaction = transaction
    return NoteRepository(database, RealAuditWriter()), transaction


def create(repository, **overrides):
    kwargs = {
        "request_id": "req-1",
        "ticket_number": "TKT-1001",
        "body": "Customer confirmed damage.",
        "expected_status": "open",
        "user_id": ALICE_UUID,
        "organization_id": CEDAR,
        "roles": ["support_agent"],
        "policy_version": "2026-09-07.1",
        "resource_id": "TKT-1001",
    }
    kwargs.update(overrides)
    return repository.create(**kwargs)


# --- the transactional guarantee -----------------------------------------------------------------
def test_note_and_audit_commit_together(created_row):
    repository, transaction = build(FakeCursor(insert_returns=created_row))
    note = create(repository)

    assert note.note_id == "note-1"
    assert transaction.committed is True
    statements = " ".join(transaction.cursor.statements)
    assert "app.internal_notes" in statements
    assert "app.audit_events" in statements


def test_audit_failure_rolls_the_note_back(created_row):
    """The whole point: no business effect without evidence."""
    repository, transaction = build(
        FakeCursor(insert_returns=created_row, fail_on_audit=True)
    )

    with pytest.raises(psycopg.Error):
        create(repository)

    assert transaction.committed is False
    assert transaction.rolled_back is True


def test_audit_is_written_after_the_note_in_the_same_transaction(created_row):
    repository, transaction = build(FakeCursor(insert_returns=created_row))
    create(repository)

    statements = transaction.cursor.statements
    note_index = next(i for i, s in enumerate(statements) if "app.internal_notes" in s)
    audit_index = next(i for i, s in enumerate(statements) if "app.audit_events" in s)
    assert note_index < audit_index


# --- authorship ----------------------------------------------------------------------------------
def test_author_is_the_verified_subject(created_row):
    """`create` takes no author parameter; the id it binds is the caller's."""
    repository, transaction = build(FakeCursor(insert_returns=created_row))
    create(repository)
    assert transaction.context["user_id"] == ALICE_UUID


def test_request_context_carries_tenant_and_roles(created_row):
    repository, transaction = build(FakeCursor(insert_returns=created_row))
    create(repository)
    assert transaction.context["organization_id"] == CEDAR
    assert transaction.context["roles"] == ["support_agent"]


def test_write_transaction_is_not_read_only(created_row):
    repository, transaction = build(FakeCursor(insert_returns=created_row))
    create(repository)
    assert transaction.context.get("read_only", False) is False


# --- stale and refused writes --------------------------------------------------------------------
def test_no_matching_ticket_raises_stale():
    """No row returned means the ticket did not match the number *and* the expected status."""
    repository, _ = build(FakeCursor(insert_returns=None))
    with pytest.raises(StaleTicketError):
        create(repository)


def test_row_policy_refusal_is_reported_as_stale(created_row):
    """A policy refusal must not surface as a database error."""

    class RefusingCursor(FakeCursor):
        def execute(self, statement, params=None):
            self.statements.append(statement)
            if "app.internal_notes" in statement:
                raise psycopg.errors.InsufficientPrivilege("row policy refused the insert")

    repository, _ = build(RefusingCursor(insert_returns=created_row))
    with pytest.raises(StaleTicketError):
        create(repository)


def test_stale_and_absent_are_indistinguishable():
    """Both raise the same error, so a caller cannot probe for a ticket's existence or state."""
    absent, _ = build(FakeCursor(insert_returns=None))
    stale, _ = build(FakeCursor(insert_returns=None))

    with pytest.raises(StaleTicketError) as first:
        create(absent)
    with pytest.raises(StaleTicketError) as second:
        create(stale, expected_status="resolved")

    assert type(first.value) is type(second.value)
    assert str(first.value) == str(second.value) == ""


# --- what reaches the audit row ------------------------------------------------------------------
def test_audit_event_records_policy_version_and_note_reference(created_row):
    captured = {}

    class CapturingAudit:
        def record_in(self, cursor, event):
            captured.update(event.as_params())
            cursor.execute("INSERT INTO app.audit_events (...)", None)

    transaction = FakeTransaction(FakeCursor(insert_returns=created_row))

    class FakeDatabase:
        pass

    database = FakeDatabase()
    database.transaction = transaction
    repository = NoteRepository(database, CapturingAudit())
    create(repository)

    assert captured["action"] == "note.create"
    assert captured["decision"] == "succeeded"
    assert captured["policy_version"] == "2026-09-07.1"
    assert captured["result_reference"] == "note-1"
    assert captured["actor_id"] == ALICE_UUID


def test_note_body_never_reaches_the_audit_row(created_row):
    """Evidence records that a note was created, not what it said."""
    captured = {}

    class CapturingAudit:
        def record_in(self, cursor, event):
            captured.update(event.as_params())
            cursor.execute("INSERT INTO app.audit_events (...)", None)

    transaction = FakeTransaction(FakeCursor(insert_returns=created_row))

    class FakeDatabase:
        pass

    database = FakeDatabase()
    database.transaction = transaction
    repository = NoteRepository(database, CapturingAudit())
    create(repository, body="sensitive customer detail that must not be duplicated")

    assert "sensitive customer detail" not in str(captured)
