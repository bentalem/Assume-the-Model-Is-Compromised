# Policy unit tests (TS-2). A bundle whose tests do not pass cannot be published.

package supportpilot.authz_test

import rego.v1

import data.supportpilot.authz

# ------------------------------------------------------------------------------------------------
# Fixtures. Mirrors the fixed test data baseline (SP-PLAN-003 §2).
# ------------------------------------------------------------------------------------------------
alice(roles) := {
	"id": "a1111111-1111-1111-1111-111111111111",
	"organizations": ["11111111-1111-1111-1111-111111111111"],
	"roles": roles,
	"authentication_level": "mfa",
}

cedar_order := {
	"type": "order",
	"id": "ORD-2001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"status": "shipped",
	"currency": "USD",
	"total_amount": "149.90",
}

northwind_order := {
	"type": "order",
	"id": "ORD-3001",
	"organization_id": "22222222-2222-2222-2222-222222222222",
	"status": "paid",
	"currency": "EUR",
	"total_amount": "512.00",
}

ctx := {"request_id": "req-test", "occurred_at": "2026-10-08T10:15:00Z", "network_zone": "internal"}

order_read(subject, resource) := {
	"subject": subject,
	"action": "order.read",
	"resource": resource,
	"context": ctx,
}

# ------------------------------------------------------------------------------------------------
# order.read — allow
# ------------------------------------------------------------------------------------------------
test_agent_reads_own_tenant_order if {
	d := authz.decision with input as order_read(alice(["support_agent"]), cedar_order)
	d.allow
	d.reason == "same_organization_and_allowed_role"
	d.policy_version == authz.policy_version
}

test_manager_reads_own_tenant_order if {
	d := authz.decision with input as order_read(alice(["support_manager"]), cedar_order)
	d.allow
}

test_auditor_reads_own_tenant_order if {
	d := authz.decision with input as order_read(alice(["auditor"]), cedar_order)
	d.allow
}

test_allow_returns_field_obligations if {
	d := authz.decision with input as order_read(alice(["support_agent"]), cedar_order)
	d.obligations.allowed_fields == authz.order_fields
}

# The obligation is a whitelist: fields the API must not return are absent from it.
test_obligations_exclude_unlisted_fields if {
	d := authz.decision with input as order_read(alice(["support_agent"]), cedar_order)
	not "customer_id" in d.obligations.allowed_fields
	not "organization_id" in d.obligations.allowed_fields
	not "id" in d.obligations.allowed_fields
}

# ------------------------------------------------------------------------------------------------
# order.read — deny
# ------------------------------------------------------------------------------------------------
test_agent_cannot_read_other_tenant_order if {
	d := authz.decision with input as order_read(alice(["support_agent"]), northwind_order)
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

test_role_without_read_permission_is_denied if {
	d := authz.decision with input as order_read(alice(["finance_approver"]), cedar_order)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

test_no_roles_is_denied if {
	d := authz.decision with input as order_read(alice([]), cedar_order)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

# Cross-tenant beats wrong-role: a user outside the tenant learns nothing about roles.
test_cross_tenant_and_wrong_role_reports_tenant_reason if {
	d := authz.decision with input as order_read(alice(["finance_approver"]), northwind_order)
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

# ------------------------------------------------------------------------------------------------
# Default deny
# ------------------------------------------------------------------------------------------------
test_unknown_action_is_default_deny if {
	d := authz.decision with input as {
		"subject": alice(["support_agent"]),
		"action": "order.delete",
		"resource": cedar_order,
		"context": ctx,
	}
	not d.allow
	d.reason == "default_deny"
}

test_empty_input_is_default_deny if {
	d := authz.decision with input as {}
	not d.allow
	d.reason == "default_deny"
}

# A model-supplied claim of being an administrator is not a role and grants nothing (T-003).
test_administrator_claim_grants_nothing if {
	d := authz.decision with input as {
		"subject": alice(["administrator", "admin", "root"]),
		"action": "order.read",
		"resource": northwind_order,
		"context": ctx,
	}
	not d.allow
}

# ------------------------------------------------------------------------------------------------
# Shape. Every decision is complete and usable by the audit trail.
# ------------------------------------------------------------------------------------------------
test_every_decision_carries_reason_and_version if {
	inputs := [
		order_read(alice(["support_agent"]), cedar_order),
		order_read(alice(["support_agent"]), northwind_order),
		order_read(alice(["finance_approver"]), cedar_order),
		{"subject": alice([]), "action": "nope", "resource": {}, "context": ctx},
	]
	every i in inputs {
		d := authz.decision with input as i
		is_string(d.reason)
		d.policy_version == authz.policy_version
		is_boolean(d.allow)
	}
}

# The default rule must spell out the version literally (Rego forbids a var there). This guards the
# duplication: if policy_version is bumped and the default rule is not, every denial would report a
# stale version into the audit trail.
test_default_deny_version_matches_constant if {
	d := authz.decision with input as {}
	d.policy_version == authz.policy_version
}
