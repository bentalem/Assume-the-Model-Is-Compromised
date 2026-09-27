"""The HTTP surface: what is refused before any store is touched, and the error model."""

from __future__ import annotations

from .conftest import API_AUDIENCE

SESSION = "0f6a1c2e-3b4d-4e5f-8a9b-0c1d2e3f4a5b"


def test_no_token_is_refused(client):
    response = client.get(f"/v1/sessions/{SESSION}/turns")
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "unauthenticated", "request_id": "mem-unassigned"}}


def test_a_token_for_the_api_only_is_refused(client, make_token):
    response = client.get(f"/v1/sessions/{SESSION}/turns",
                          headers={"Authorization": f"Bearer {make_token(aud=API_AUDIENCE)}"})
    assert response.status_code == 401


def test_identity_in_the_body_is_refused_not_ignored(client, make_token):
    """Rule 1: no user_id anywhere. Refused outright, so a caller learns it cannot be done."""
    response = client.post("/v1/sessions", json={"title": "x", "user_id": "bob"},
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400
    rejected = response.json()["error"]["rejected"]
    assert rejected == [{"field": "body.user_id", "error": "extra_forbidden"}]


def test_a_rejected_value_is_never_echoed(client, make_token):
    """A rejected body is caller content — here, possibly something somebody wanted remembered."""
    phrase = "please-remember-this-exact-phrase"
    response = client.post(f"/v1/sessions/{SESSION}/turns",
                           json={"role": "not-a-role", "content": phrase},
                           headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400
    assert phrase not in response.text
    assert "not-a-role" not in response.text


def test_an_unknown_query_parameter_is_refused(client, make_token):
    response = client.get(f"/v1/sessions/{SESSION}/turns?owner=bob",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400


def test_a_malformed_session_id_is_refused_before_the_store(client, make_token):
    response = client.get("/v1/sessions/not-a-uuid/turns",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400


def test_page_size_is_bounded(client, make_token):
    response = client.get(f"/v1/sessions/{SESSION}/turns?limit=5000",
                          headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 400


def test_the_runtime_routes_are_not_in_the_action_document(client):
    """History is for an agent runtime, never for the model — so it must not be published to it."""
    document = client.get("/openapi.json").json()
    assert not any(path.startswith("/v1/sessions") for path in document.get("paths", {}))
