"""TS-2 (client side) — every abnormal policy outcome is a deny.

The bundle's own rules are tested in policy/tests. What is tested here is the client's contract:
that nothing other than an explicit, well-formed `allow: true` ever authorizes a request.
"""

from __future__ import annotations

import httpx
import pytest

from supportpilot_api.policy.client import (
    REASON_MALFORMED,
    REASON_UNAVAILABLE,
    PolicyClient,
)

URL = "http://opa:8181/v1/data/supportpilot/authz/decision"

SUBJECT = {"id": "alice", "organizations": ["cedar"], "roles": ["support_agent"]}
RESOURCE = {"type": "order", "id": "ORD-2001", "organization_id": "cedar"}
CONTEXT = {"request_id": "req-1"}


def client_returning(handler) -> PolicyClient:
    client = PolicyClient(URL, timeout_ms=250)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def decide(client: PolicyClient):
    return client.decide(
        subject=SUBJECT, action="order.read", resource=RESOURCE, context=CONTEXT
    )


def json_response(payload, status: int = 200):
    return lambda request: httpx.Response(status, json=payload)


# Allow ---------------------------------------------------------------------------------------
def test_well_formed_allow_is_honoured():
    result = decide(
        client_returning(
            json_response(
                {
                    "result": {
                        "allow": True,
                        "reason": "same_organization_and_allowed_role",
                        "policy_version": "2026-09-07.1",
                        "obligations": {"allowed_fields": ["order_number", "status"]},
                    }
                }
            )
        )
    )
    assert result.allow is True
    assert result.allowed_fields == ["order_number", "status"]
    assert result.unavailable is False


def test_allow_without_obligations_is_honoured():
    result = decide(
        client_returning(
            json_response(
                {"result": {"allow": True, "reason": "ok", "policy_version": "1"}}
            )
        )
    )
    assert result.allow is True
    assert result.allowed_fields is None


# Explicit deny -------------------------------------------------------------------------------
def test_explicit_deny_is_not_an_outage():
    result = decide(
        client_returning(
            json_response(
                {
                    "result": {
                        "allow": False,
                        "reason": "not_a_member_of_resource_organization",
                        "policy_version": "2026-09-07.1",
                    }
                }
            )
        )
    )
    assert result.allow is False
    assert result.unavailable is False
    assert result.reason == "not_a_member_of_resource_organization"


# Dependency failure — TS2-05 -----------------------------------------------------------------
def test_timeout_is_deny_and_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    result = decide(client_returning(handler))
    assert result.allow is False
    assert result.unavailable is True
    assert result.reason == REASON_UNAVAILABLE


def test_connection_error_is_deny_and_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    result = decide(client_returning(handler))
    assert result.allow is False
    assert result.unavailable is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500, 502, 503])
def test_non_200_is_deny(status):
    result = decide(client_returning(json_response({"result": {"allow": True}}, status)))
    assert result.allow is False
    assert result.unavailable is True


# Malformed — TS2-04 --------------------------------------------------------------------------
def test_undefined_decision_is_deny():
    """An undefined document omits `result` entirely."""
    result = decide(client_returning(json_response({})))
    assert result.allow is False
    assert result.reason == REASON_MALFORMED


def test_unparseable_body_is_deny():
    result = decide(client_returning(lambda r: httpx.Response(200, content=b"<html>nope")))
    assert result.allow is False
    assert result.reason == REASON_MALFORMED


def test_missing_allow_is_deny():
    result = decide(
        client_returning(json_response({"result": {"reason": "x", "policy_version": "1"}}))
    )
    assert result.allow is False


@pytest.mark.parametrize("truthy", ["true", 1, "yes", [1], {"a": 1}, "allow"])
def test_truthy_non_boolean_allow_does_not_authorize(truthy):
    """`allow` must be boolean true. A truthy string or number is malformed, not permission."""
    result = decide(
        client_returning(
            json_response({"result": {"allow": truthy, "reason": "x", "policy_version": "1"}})
        )
    )
    assert result.allow is False
    assert result.reason == REASON_MALFORMED


def test_missing_reason_is_deny():
    result = decide(
        client_returning(json_response({"result": {"allow": True, "policy_version": "1"}}))
    )
    assert result.allow is False


def test_missing_policy_version_is_deny():
    """Without a version the decision cannot be evidenced, so it cannot be honoured."""
    result = decide(client_returning(json_response({"result": {"allow": True, "reason": "x"}})))
    assert result.allow is False


def test_non_dict_obligations_is_deny():
    result = decide(
        client_returning(
            json_response(
                {
                    "result": {
                        "allow": True,
                        "reason": "x",
                        "policy_version": "1",
                        "obligations": ["order_number"],
                    }
                }
            )
        )
    )
    assert result.allow is False


def test_malformed_allowed_fields_is_ignored_not_trusted():
    """A non-list of strings yields no whitelist, so minimization falls back to returning nothing
    extra rather than trusting a broken obligation."""
    result = decide(
        client_returning(
            json_response(
                {
                    "result": {
                        "allow": True,
                        "reason": "x",
                        "policy_version": "1",
                        "obligations": {"allowed_fields": [1, 2, 3]},
                    }
                }
            )
        )
    )
    assert result.allow is True
    assert result.allowed_fields is None


# The input sent to OPA ------------------------------------------------------------------------
def test_input_is_wrapped_and_complete():
    captured = {}

    def handler(request):
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(
            200, json={"result": {"allow": True, "reason": "x", "policy_version": "1"}}
        )

    decide(client_returning(handler))
    assert set(captured) == {"input"}
    assert set(captured["input"]) == {"subject", "action", "resource", "context"}
    assert captured["input"]["action"] == "order.read"
