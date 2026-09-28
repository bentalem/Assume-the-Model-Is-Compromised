"""The gateway: mint per call inside the ceiling, refuse outside it, and passthrough when armed."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from delegation_broker.exchange import TOKEN_TYPE_ACCESS, GRANT_TYPE
from delegation_broker.main import create_app

from .conftest import ALICE_SUB, AUDIENCE, BROKER, claims_of


@pytest.fixture
def client(broker) -> TestClient:
    return TestClient(create_app(broker))


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def forwarded_token(api) -> str:
    return api.requests[-1].headers["authorization"].split(" ", 1)[1]


def test_a_call_inside_the_ceiling_is_forwarded_with_a_token_minted_for_it(client, api, user_token):
    response = client.get("/status-helper/v1/orders/ORD-2001", headers=bearer(user_token()))
    assert response.status_code == 200
    sent = api.requests[-1]
    assert str(sent.url) == "http://api:8000/v1/orders/ORD-2001"
    claims = claims_of(forwarded_token(api))
    assert claims["sub"] == ALICE_SUB
    assert claims["act"] == {"sub": "status-helper"}
    assert claims["scope"] == "orders:read"
    assert claims["exp"] - claims["iat"] <= 60
    assert response.headers["x-delegation"].startswith("minted; actor=status-helper; scope=orders:read")


def test_the_minted_token_verifies_against_the_published_key(client, api, user_token):
    client.get("/status-helper/v1/orders/ORD-2001", headers=bearer(user_token()))
    published = client.get("/.well-known/jwks.json").json()["keys"][0]
    claims = jwt.decode(forwarded_token(api), published, algorithms=["ES256"],
                        audience=AUDIENCE, issuer=BROKER)
    assert claims["act"]["sub"] == "status-helper"


def test_a_call_outside_the_ceiling_is_refused_and_never_forwarded(client, api, user_token):
    response = client.get("/status-helper/v1/customers/CUS-4001", headers=bearer(user_token()))
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "scope_exceeds_profile"}}
    assert api.requests == []


def test_the_query_string_and_body_are_forwarded_unchanged(client, api, user_token):
    client.get("/refund-assistant/v1/orders/ORD-2001?include_items=true", headers=bearer(user_token()))
    assert api.requests[-1].url.query == b"include_items=true"
    body = b'{"order_number":"ORD-2001","amount":"12.00","currency":"USD","reason":"damaged_on_arrival"}'
    client.post("/refund-assistant/v1/actions/refunds", headers={**bearer(user_token()),
                "Content-Type": "application/json"}, content=body)
    assert api.requests[-1].content == body
    assert claims_of(forwarded_token(api))["scope"] == "refunds:propose"


def test_armed_passthrough_forwards_the_users_own_token(client, api, user_token, arm):
    arm(broker_passthrough=True)
    token = user_token()
    response = client.get("/status-helper/v1/customers/CUS-4001", headers=bearer(token))
    assert response.status_code == 200
    assert forwarded_token(api) == token
    assert response.headers["x-delegation"] == "passthrough"


def test_a_malformed_settings_file_keeps_the_gateway_secure(client, api, user_token, settings_path):
    settings_path.write_text("{ not json")
    response = client.get("/status-helper/v1/customers/CUS-4001", headers=bearer(user_token()))
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/nobody/v1/orders/ORD-2001", 404, "unknown_profile"),
        ("/status-helper/v1/orders/ORD-2001/secret", 404, "unknown_operation"),
        ("/status-helper/v1/internal/approvals/x", 404, "unknown_operation"),
    ],
)
def test_unknown_profiles_and_operations_are_refused(client, api, user_token, path, status, code):
    response = client.get(path, headers=bearer(user_token()))
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert api.requests == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer x.y.z"}])
def test_a_call_without_a_valid_user_token_is_refused(client, api, headers):
    response = client.get("/status-helper/v1/orders/ORD-2001", headers=headers)
    assert response.status_code == 401
    assert api.requests == []


def test_a_delegated_token_is_not_accepted_as_a_users_token(client, api, user_token):
    client.get("/status-helper/v1/orders/ORD-2001", headers=bearer(user_token()))
    minted = forwarded_token(api)
    response = client.get("/refund-assistant/v1/orders/ORD-2001", headers=bearer(minted))
    assert response.status_code == 401


# --- the exchange endpoint, over HTTP ------------------------------------------------------------------
def test_the_exchange_endpoint_accepts_basic_client_authentication(client, user_token):
    credentials = base64.b64encode(b"status-helper:status_helper-test-credential").decode()
    response = client.post(
        "/oauth/token",
        headers={"Authorization": f"Basic {credentials}"},
        data={"grant_type": GRANT_TYPE, "subject_token": user_token(),
              "subject_token_type": TOKEN_TYPE_ACCESS, "scope": "orders:read"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert claims_of(response.json()["access_token"])["act"] == {"sub": "status-helper"}


def test_the_exchange_endpoint_refuses_a_wrong_credential(client, user_token):
    response = client.post("/oauth/token", data={
        "grant_type": GRANT_TYPE, "client_id": "status-helper", "client_secret": "guess",
        "subject_token": user_token(), "subject_token_type": TOKEN_TYPE_ACCESS, "scope": "orders:read"})
    assert (response.status_code, response.json()["error"]) == (401, "invalid_client")


def test_a_repeated_parameter_is_refused(client, user_token):
    response = client.post(
        "/oauth/token",
        content=f"grant_type={GRANT_TYPE}&scope=orders:read&scope=customers:read".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400


def test_the_exchange_endpoint_wants_a_form(client):
    assert client.post("/oauth/token", json={"grant_type": GRANT_TYPE}).status_code == 400
