"""Rules and context assembly: the service's own decisions, with the stores stubbed.

What is proven here is the logic this service owns — who it refuses before the store is asked,
that every refusal leaves audit evidence, and how the context block is built from what the store
returned: labels, re-authorisation of history, and what the log records. Separation of duty in the
store (the trigger), row-level security and the cross-tenant cases are proven against memory-db by
its smoke tests and scripts/memory_suite.py, not here.
"""

from __future__ import annotations

import pytest

from .conftest import CEDAR, RecordingCursor

RULE = "0f6a1c2e-3b4d-4e5f-8a9b-0c1d2e3f4a5b"
SESSION = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
CONTEXT_ID = "9f8e7d6c-5b4a-4938-8271-605f4e3d2c1b"


def _audit_reasons(cursor: RecordingCursor) -> list[str]:
    return [params[-1] for query, params in cursor.executed if "INSERT INTO mem.audit_events" in query]


def _statements(cursor: RecordingCursor, fragment: str) -> list[tuple]:
    return [params for query, params in cursor.executed if fragment in query]


def _use(client, cursor: RecordingCursor) -> None:
    client.app.state.services.db.cursor = cursor


# ------------------------------------------------------------------------------------------------
# Rules
# ------------------------------------------------------------------------------------------------

def test_a_non_approver_cannot_decide_and_the_refusal_is_recorded(client, make_token):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.post(f"/v1/rules/proposals/{RULE}/decision",
                           json={"decision": "approve", "payload_hash": "a" * 64},
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 403
    assert _audit_reasons(cursor) == ["not_an_approver"]
    assert not _statements(cursor, "UPDATE mem.rules")


def test_a_non_approver_cannot_retire_and_the_refusal_is_recorded(client, make_token):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.post(f"/v1/rules/{RULE}/retirement",
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 403
    assert _audit_reasons(cursor) == ["not_an_approver"]
    assert not _statements(cursor, "UPDATE mem.rules")


def test_a_proposal_is_born_proposed_and_attributed_to_the_agent(client, make_token):
    cursor = RecordingCursor({"mem.setting": {"value": "false"}, "INSERT INTO mem.rules": {"id": RULE}})
    _use(client, cursor)
    response = client.post("/v1/rules/proposals", json={"text": "Greet the customer by name."},
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 201
    assert response.json() == {"rule_id": RULE, "state": "proposed"}
    (org, _text, state, proposer, _hash), = _statements(cursor, "INSERT INTO mem.rules")
    assert (org, state, proposer) == (CEDAR, "proposed", "alice-id")
    assert "'agent'" in next(q for q, _ in cursor.executed if "INSERT INTO mem.rules" in q)


@pytest.mark.parametrize("body", [
    {"decision": "maybe", "payload_hash": "a" * 64},
    {"decision": "approve", "payload_hash": "not-a-hash"},
    {"decision": "approve", "payload_hash": "a" * 64, "decided_by": "bob"},
])
def test_a_malformed_decision_never_reaches_the_store(client, make_token, body):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.post(f"/v1/rules/proposals/{RULE}/decision", json=body,
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400
    assert cursor.executed == []


def test_the_action_document_is_the_four_model_operations(client):
    document = client.get("/openapi.json").json()
    operations = {op["operationId"] for item in document["paths"].values() for op in item.values()}
    assert operations == {"remember", "recall", "forget", "propose_rule"}
    assert not any("422" in op["responses"] for item in document["paths"].values()
                   for op in item.values())


# ------------------------------------------------------------------------------------------------
# Context
# ------------------------------------------------------------------------------------------------

def _context_cursor(setting: str, turns: list[dict]) -> RecordingCursor:
    return RecordingCursor({
        "mem.setting": {"value": setting},
        "FROM mem.rules": [],
        "FROM mem.records": [{"id": "m-1", "content": "Prefers email.", "channel": "agent",
                              "confirmed_via": "user", "derived_from": None, "created_at": None}],
        "FROM mem.turns": turns,
        "INSERT INTO mem.context_log": {"id": CONTEXT_ID},
    })


def _turn(role: str, content: str, roles: list[str], seq: int = 1) -> dict:
    return {"session_id": SESSION, "seq": seq, "role": role, "content": content,
            "authz": {"roles": roles}, "created_at": None}


def _logged_items(cursor: RecordingCursor) -> list[dict]:
    (params,) = _statements(cursor, "INSERT INTO mem.context_log")
    return params[-1].obj


def test_a_tool_turn_from_a_role_no_longer_held_is_dropped_and_the_block_says_so(client, make_token):
    cursor = _context_cursor("on", [_turn("tool", "CUS-4003 email: x@example.test",
                                          ["support_manager"])])
    _use(client, cursor)
    response = client.post("/v1/context", json={"query": "what next"},
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 200
    body = response.json()
    assert "x@example.test" not in body["rendered"]
    assert "support_manager, which you no longer hold" in body["rendered"]
    assert body["omitted"] == 1
    (turn,) = [i for i in _logged_items(cursor) if i["kind"] == "turn"]
    assert turn["included"] is False and "content" not in turn


def test_with_revalidation_off_the_turn_outlives_its_permission(client, make_token):
    cursor = _context_cursor("off", [_turn("tool", "CUS-4003 email: x@example.test",
                                           ["support_manager"])])
    _use(client, cursor)
    body = client.post("/v1/context", json={"query": "what next"},
                       headers={"Authorization": f"Bearer {make_token()}"}).json()
    assert "x@example.test" in body["rendered"]
    (turn,) = [i for i in _logged_items(cursor) if i["kind"] == "turn"]
    assert turn["outlived_its_permission"] is True
    assert turn["produced_under"] == ["support_manager"]
    assert turn["caller_roles_now"] == ["support_agent"]


def test_a_user_turn_is_not_re_authorised(client, make_token):
    """What the user typed carries nothing the system retrieved, so no role gates it."""
    cursor = _context_cursor("on", [_turn("user", "Where is my order?", ["support_manager"])])
    _use(client, cursor)
    body = client.post("/v1/context", json={"query": "what next"},
                       headers={"Authorization": f"Bearer {make_token()}"}).json()
    assert "Where is my order?" in body["rendered"] and body["omitted"] == 0


def test_provenance_labels_every_item_and_off_removes_them(client, make_token):
    for setting, labelled in (("on", True), ("off", False)):
        cursor = _context_cursor(setting, [])
        _use(client, cursor)
        rendered = client.post("/v1/context", json={"query": "q"},
                               headers={"Authorization": f"Bearer {make_token()}"}).json()["rendered"]
        assert "Prefers email." in rendered
        assert ("(memory; written by agent; confirmed by user; original)" in rendered) is labelled


def test_the_block_and_its_audit_event_are_written_together(client, make_token):
    cursor = _context_cursor("on", [])
    _use(client, cursor)
    client.post("/v1/context", json={"query": "q"},
                headers={"Authorization": f"Bearer {make_token()}"})
    statements = [q for q, _ in cursor.executed]
    log_at = next(i for i, q in enumerate(statements) if "INSERT INTO mem.context_log" in q)
    assert "INSERT INTO mem.audit_events" in statements[log_at + 1]
    (params,) = [p for q, p in cursor.executed if "INSERT INTO mem.audit_events" in q]
    assert params[6] == CONTEXT_ID and params[4] == "context.assemble"


@pytest.mark.parametrize("body", [
    {"query": ""},
    {"query": "q", "session_id": "not-a-session"},
    {"query": "q", "user_id": "bob"},
    {"query": "x" * 501},
])
def test_a_malformed_context_request_never_reaches_the_store(client, make_token, body):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.post("/v1/context", json=body,
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400
    assert cursor.executed == []


# ------------------------------------------------------------------------------------------------
# The runtime's two read views: an approver's queue, and what waits for a user's confirmation
# ------------------------------------------------------------------------------------------------

def test_a_non_approver_cannot_read_the_review_queue_and_the_refusal_is_recorded(client, make_token):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.get("/v1/rules/review?state=proposed",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 403
    assert _audit_reasons(cursor) == ["not_an_approver"]
    assert not _statements(cursor, "FROM mem.rules")


@pytest.mark.parametrize("query", ["", "?state=retired", "?state=proposed&org=northwind"])
def test_a_malformed_review_request_never_reaches_the_store(client, make_token, query):
    cursor = RecordingCursor()
    _use(client, cursor)
    response = client.get(f"/v1/rules/review{query}",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400
    assert cursor.executed == []


def test_pending_lists_only_unconfirmed_and_records_the_read(client, make_token):
    from datetime import datetime, timezone

    rows = [{"id": "m-2", "content": "Escalated to team-north.", "channel": "agent",
             "created_at": datetime(2026, 9, 27, tzinfo=timezone.utc)}]
    cursor = RecordingCursor({"FROM mem.records": rows})
    _use(client, cursor)
    response = client.get("/v1/memories/pending",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 200
    assert response.json()["pending"][0]["memory_id"] == "m-2"
    (query, _), = [(q, p) for q, p in cursor.executed if "FROM mem.records" in q]
    assert "status = 'unconfirmed'" in query
    assert _audit_reasons(cursor) == ["1_pending"]


def test_the_runtime_read_views_are_not_in_the_action_document(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/memories/pending" not in paths and "/v1/rules/review" not in paths
