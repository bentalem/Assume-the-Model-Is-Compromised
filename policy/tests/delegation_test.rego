# Policy tests for delegated requests (track 1, challenges 1.5 - 1.8).
#
# A separate file on purpose: authz_test.rego is the proof that a request with no `delegation`
# behaves exactly as it did before delegation existed, and it is not edited to make room for this.

package supportpilot.delegation_test

import rego.v1

import data.supportpilot.authz

CEDAR := "11111111-1111-1111-1111-111111111111"

NORTHWIND := "22222222-2222-2222-2222-222222222222"

ALICE := "a1111111-1111-1111-1111-111111111111"

FIONA := "f1111111-1111-1111-1111-111111111111"

subject(id, roles) := {
	"id": id,
	"organizations": [CEDAR],
	"roles": roles,
	"authentication_level": "mfa",
}

ctx := {"request_id": "req-delegation", "occurred_at": "2026-10-08T10:15:00Z", "network_zone": "internal"}

order(org) := {
	"type": "order",
	"id": "ORD-2001",
	"organization_id": org,
	"status": "shipped",
	"currency": "USD",
	"total_amount": "149.90",
	"requested_amount": "49.90",
	"requested_currency": "USD",
}

customer := {"type": "customer", "id": "CUS-4001", "organization_id": CEDAR, "sensitivity": "normal"}

pending_action(requester) := {
	"type": "action_request",
	"id": "9c1f0000-0000-0000-0000-000000000001",
	"organization_id": CEDAR,
	"requester_id": requester,
	"expires_at": "2026-12-31T00:00:00Z",
	"state": "PENDING_APPROVAL",
}

delegation(scopes) := {"actor": "status-helper", "chain": ["status-helper"], "scopes": scopes}

request(subj, action, resource, scopes) := {
	"subject": subj,
	"action": action,
	"resource": resource,
	"context": ctx,
	"delegation": delegation(scopes),
}

# --- inside the scope: exactly the answer the user would get ------------------------------------
test_delegated_read_inside_scope_is_allowed_with_the_same_reason_and_fields if {
	plain := authz.decision with input as {
		"subject": subject(ALICE, ["support_agent"]),
		"action": "order.read",
		"resource": order(CEDAR),
		"context": ctx,
	}
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "order.read", order(CEDAR), ["orders:read"],
	)
	d == plain
	d.allow
}

test_delegated_proposal_inside_scope_still_requires_approval if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "refund.propose", order(CEDAR), ["refunds:propose"],
	)
	d.allow
	d.obligations.requires_approval == true
}

# --- outside the scope: refused, whatever the user may do ---------------------------------------
test_delegated_read_outside_scope_is_refused if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "customer.read", customer, ["orders:read"],
	)
	not d.allow
	d.reason == "scope_not_granted"
	d.policy_version == authz.policy_version
}

test_delegated_search_needs_customers_read_too if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "customer.search",
		{"type": "organization", "id": CEDAR, "organization_id": CEDAR}, ["orders:read"],
	)
	d.reason == "scope_not_granted"
}

test_empty_scope_grants_nothing if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "order.read", order(CEDAR), [],
	)
	d.reason == "scope_not_granted"
}

test_delegation_without_a_scope_list_grants_nothing if {
	d := authz.decision with input as {
		"subject": subject(ALICE, ["support_agent"]),
		"action": "order.read",
		"resource": order(CEDAR),
		"context": ctx,
		"delegation": {"actor": "status-helper", "chain": ["status-helper"]},
	}
	d.reason == "scope_not_granted"
}

test_a_scope_string_is_not_a_scope_list if {
	d := authz.decision with input as {
		"subject": subject(ALICE, ["support_agent"]),
		"action": "order.read",
		"resource": order(CEDAR),
		"context": ctx,
		"delegation": {"actor": "status-helper", "chain": ["status-helper"], "scopes": "orders:read"},
	}
	not d.allow
}

# --- the intersection, from the other side: a scope never adds what the roles do not give --------
test_scope_does_not_replace_a_missing_role if {
	d := authz.decision with input as request(
		subject(ALICE, ["finance_approver"]), "order.read", order(CEDAR), ["orders:read"],
	)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

test_scope_does_not_cross_a_tenant if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "order.read", order(NORTHWIND), ["orders:read"],
	)
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

test_scope_does_not_raise_a_refund_limit if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "refund.propose",
		object.union(order(CEDAR), {"requested_amount": "450.00"}), ["refunds:propose"],
	)
	d.reason == "amount_exceeds_role_limit"
}

# --- the agent ceiling at the resource server -----------------------------------------------------
test_an_agent_cannot_approve_even_holding_the_scope if {
	d := authz.decision with input as request(
		subject(FIONA, ["finance_approver"]), "refund.approve", pending_action(ALICE), ["refunds:approve"],
	)
	not d.allow
	d.reason == "agent_cannot_approve"
}

test_an_agent_cannot_approve_without_the_scope_either if {
	d := authz.decision with input as request(
		subject(FIONA, ["finance_approver"]), "refund.approve", pending_action(ALICE), ["orders:read"],
	)
	d.reason == "agent_cannot_approve"
}

test_the_same_approval_without_an_agent_is_still_allowed if {
	d := authz.decision with input as {
		"subject": subject(FIONA, ["finance_approver"]),
		"action": "refund.approve",
		"resource": pending_action(ALICE),
		"context": ctx,
	}
	d.allow
}

test_self_approval_through_an_agent_is_still_refused if {
	d := authz.decision with input as request(
		subject(ALICE, ["finance_approver"]), "refund.approve", pending_action(ALICE), ["refunds:approve"],
	)
	not d.allow
}

# --- the scope table itself ----------------------------------------------------------------------
decided_actions := {
	"order.read", "customer.search", "customer.read", "ticket.read",
	"note.create", "refund.propose", "refund.approve", "action.read",
}

test_every_action_the_policy_decides_has_a_scope if {
	every action in decided_actions {
		data.scopes.actions[action]
	}
}

test_the_scope_table_names_no_action_the_policy_does_not_decide if {
	every action, _ in data.scopes.actions {
		action in decided_actions
	}
}

test_approval_is_never_delegable if {
	"refunds:approve" in data.scopes.never_delegable
}

test_an_action_missing_from_the_table_is_refused_when_delegated if {
	d := authz.decision with input as request(
		subject(ALICE, ["support_agent"]), "order.read", order(CEDAR), ["orders:read"],
	)
		with data.scopes.actions as {}
	not d.allow
	d.reason == "scope_not_granted"
}
