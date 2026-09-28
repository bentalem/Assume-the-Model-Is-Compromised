"""The trusted configuration: what the broker refuses to start on, and how settings fail."""

from __future__ import annotations

import json

import pytest

from delegation_broker import operations
from delegation_broker.trusted import ConfigurationRefused, load_profiles, read_settings

from .conftest import REPO


def test_the_real_profiles_load_with_their_ceilings(profiles):
    assert profiles["status-helper"].ceiling == frozenset({"orders:read"})
    assert profiles["refund-assistant"].ceiling == frozenset(
        {"orders:read", "refunds:propose", "actions:read"}
    )


def test_no_profile_may_hold_approval(copy_profiles, secrets_dir, scopes):
    path = copy_profiles(lambda d: d["profiles"][1]["ceiling"].append("refunds:approve"))
    with pytest.raises(ConfigurationRefused, match="may never be delegated"):
        load_profiles(path, secrets_dir, scopes)


def test_a_profile_naming_an_unknown_scope_is_refused(copy_profiles, secrets_dir, scopes):
    path = copy_profiles(lambda d: d["profiles"][0]["ceiling"].append("orders:*"))
    with pytest.raises(ConfigurationRefused, match="unknown scopes"):
        load_profiles(path, secrets_dir, scopes)


def test_a_profile_without_a_mounted_credential_is_refused(profiles, secrets_dir, scopes):
    (secrets_dir / "broker_profile_status_helper").unlink()
    with pytest.raises(ConfigurationRefused, match="not mounted"):
        load_profiles(REPO / "infrastructure" / "local" / "broker" / "profiles.json",
                      secrets_dir, scopes)


def test_a_malformed_profile_name_is_refused(copy_profiles, secrets_dir, scopes):
    path = copy_profiles(lambda d: d["profiles"][0].update(name="Status Helper"))
    with pytest.raises(ConfigurationRefused, match="malformed"):
        load_profiles(path, secrets_dir, scopes)


def test_a_profile_credential_is_compared_not_leaked(profiles):
    helper = profiles["status-helper"]
    assert helper.authenticates("status_helper-test-credential")
    assert not helper.authenticates("")
    assert not helper.authenticates("refund_assistant-test-credential")
    assert "test-credential" not in repr(helper)


# --- settings ---------------------------------------------------------------------------------------
def test_absent_settings_are_secure(settings_path):
    assert read_settings(settings_path) == {
        "broker.passthrough": False, "ceiling.user_only": False, "chain.widen": False,
    }


@pytest.mark.parametrize("text", ["", "{", "[]", "null", '"broker.passthrough"'])
def test_malformed_settings_are_secure(settings_path, text):
    settings_path.write_text(text)
    assert not any(read_settings(settings_path).values())


@pytest.mark.parametrize("value", ["true", 1, "yes", "True", None])
def test_only_the_literal_true_arms_a_setting(settings_path, value):
    settings_path.write_text(json.dumps({"broker.passthrough": value}))
    assert read_settings(settings_path)["broker.passthrough"] is False


def test_true_arms_exactly_the_setting_named(settings_path):
    settings_path.write_text(json.dumps({"chain.widen": True, "unknown.switch": True}))
    assert read_settings(settings_path) == {
        "broker.passthrough": False, "ceiling.user_only": False, "chain.widen": True,
    }


# --- the operation table ----------------------------------------------------------------------------
def test_the_operation_table_is_the_action_document():
    document = json.loads((REPO / "openapi" / "supportpilot-actions.json").read_text(encoding="utf-8"))
    declared = {
        (method.upper(), path, op["operationId"])
        for path, ops in document["paths"].items()
        for method, op in ops.items()
    }
    known = {(o.method, o.template, o.operation_id) for o in operations.OPERATIONS}
    assert known == declared


def test_every_operation_maps_to_an_action_the_scope_table_knows(scopes):
    for operation in operations.OPERATIONS:
        assert scopes.for_action(operation.action), operation.operation_id


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/v1/orders/ORD-2001", "get_order"),
        ("GET", "/v1/customers", "search_customers"),
        ("GET", "/v1/customers/CUS-4001", "get_customer"),
        ("POST", "/v1/tickets/TKT-1001/notes", "add_internal_note"),
        ("POST", "/v1/actions/refunds", "propose_refund"),
        ("GET", "/v1/actions/9c1f0000-0000-0000-0000-000000000001", "get_action_status"),
        ("DELETE", "/v1/orders/ORD-2001", None),
        ("GET", "/v1/orders/ORD-2001/../../internal/approvals", None),
        ("GET", "/internal/approvals/x", None),
        ("POST", "/v1/actions/9c1f/approve", None),
        ("GET", "/v1/orders/" + "A" * 65, None),
    ],
)
def test_operations_resolve_from_method_and_path_only(method, path, expected):
    resolved = operations.resolve(method, path)
    assert (resolved.operation_id if resolved else None) == expected
