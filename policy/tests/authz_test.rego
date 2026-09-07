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

# ================================================================================================
# Phase 2 — customer and ticket rules
# ================================================================================================

cedar_customer(sensitivity) := {
	"type": "customer",
	"id": "CUS-4001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"sensitivity": sensitivity,
}

northwind_customer := {
	"type": "customer",
	"id": "CUS-9001",
	"organization_id": "22222222-2222-2222-2222-222222222222",
	"sensitivity": "normal",
}

cedar_ticket := {
	"type": "ticket",
	"id": "TKT-1001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"status": "open",
	"assigned_team": "team-north",
}

act(subject, action, resource) := {
	"subject": subject,
	"action": action,
	"resource": resource,
	"context": ctx,
}

# --- customer.search ----------------------------------------------------------------------------
test_agent_may_search_own_tenant if {
	d := authz.decision with input as act(alice(["support_agent"]), "customer.search", {
		"type": "organization",
		"organization_id": "11111111-1111-1111-1111-111111111111",
	})
	d.allow
}

# The page cap lives in policy, so it can be tightened without touching application code.
test_search_carries_a_result_cap if {
	d := authz.decision with input as act(alice(["support_agent"]), "customer.search", {
		"type": "organization",
		"organization_id": "11111111-1111-1111-1111-111111111111",
	})
	d.obligations.max_results == 25
}

test_search_never_returns_contact_details if {
	d := authz.decision with input as act(alice(["support_agent"]), "customer.search", {
		"type": "organization",
		"organization_id": "11111111-1111-1111-1111-111111111111",
	})
	not "email" in d.obligations.allowed_fields
	not "open_ticket_count" in d.obligations.allowed_fields
}

test_search_denied_outside_tenant if {
	d := authz.decision with input as act(alice(["support_agent"]), "customer.search", {
		"type": "organization",
		"organization_id": "22222222-2222-2222-2222-222222222222",
	})
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

# --- customer.read ------------------------------------------------------------------------------
test_agent_reads_normal_customer_with_contact_details if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "customer.read", cedar_customer("normal"),
	)
	d.allow
	"email" in d.obligations.allowed_fields
}

# The heart of the sensitivity rule: an agent still gets an answer, minus the contact details.
test_agent_reading_restricted_customer_loses_contact_details if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "customer.read", cedar_customer("restricted"),
	)
	d.allow
	d.reason == "restricted_customer_minimal_fields"
	not "email" in d.obligations.allowed_fields
	"full_name" in d.obligations.allowed_fields
}

test_manager_reading_restricted_customer_keeps_contact_details if {
	d := authz.decision with input as act(
		alice(["support_manager"]), "customer.read", cedar_customer("restricted"),
	)
	d.allow
	"email" in d.obligations.allowed_fields
}

test_auditor_reading_restricted_customer_keeps_contact_details if {
	d := authz.decision with input as act(
		alice(["auditor"]), "customer.read", cedar_customer("restricted"),
	)
	d.allow
	"email" in d.obligations.allowed_fields
}

test_customer_read_denied_outside_tenant if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "customer.read", northwind_customer,
	)
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

test_finance_approver_may_not_read_customers if {
	d := authz.decision with input as act(
		alice(["finance_approver"]), "customer.read", cedar_customer("normal"),
	)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

# --- ticket.read --------------------------------------------------------------------------------
test_agent_may_read_own_tenant_ticket if {
	d := authz.decision with input as act(alice(["support_agent"]), "ticket.read", cedar_ticket)
	d.allow
	"messages" in d.obligations.allowed_fields
}

test_ticket_read_denied_outside_tenant if {
	d := authz.decision with input as act(alice(["support_agent"]), "ticket.read", {
		"type": "ticket",
		"id": "TKT-3001",
		"organization_id": "22222222-2222-2222-2222-222222222222",
		"status": "open",
	})
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

# --- no ambiguity -------------------------------------------------------------------------------
# customer.read has three allow arms and two deny arms. If any pair could be true at once, Rego
# raises a conflict and the API converts that to a deny — a denial nobody intended. Every
# combination of role and sensitivity must produce exactly one decision.
test_customer_read_has_exactly_one_decision_for_every_combination if {
	roles := [
		["support_agent"], ["support_manager"], ["auditor"], ["finance_approver"], [],
		["support_agent", "support_manager"], ["support_agent", "auditor"],
	]
	sensitivities := ["normal", "restricted"]
	every role in roles {
		every sensitivity in sensitivities {
			d := authz.decision with input as act(
				alice(role), "customer.read", cedar_customer(sensitivity),
			)
			is_boolean(d.allow)
			is_string(d.reason)
		}
	}
}

# A user holding both agent and manager gets the manager's view of a restricted customer: the
# broader membership wins, and the two allow arms do not collide.
test_agent_plus_manager_sees_restricted_contact_details if {
	d := authz.decision with input as act(
		alice(["support_agent", "support_manager"]), "customer.read", cedar_customer("restricted"),
	)
	d.allow
	"email" in d.obligations.allowed_fields
}

# ================================================================================================
# Phase 3 — note.create
# ================================================================================================

ticket_in_status(status) := {
	"type": "ticket",
	"id": "TKT-1001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"status": status,
	"assigned_team": "team-north",
}

test_agent_may_add_a_note_to_an_open_ticket if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "note.create", ticket_in_status("open"),
	)
	d.allow
}

test_manager_may_add_a_note if {
	d := authz.decision with input as act(
		alice(["support_manager"]), "note.create", ticket_in_status("pending"),
	)
	d.allow
}

# A closed case stops accumulating commentary. This is a business rule, so it belongs in policy
# rather than in application code where it would be invisible to review.
test_no_notes_on_a_closed_ticket if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "note.create", ticket_in_status("closed"),
	)
	not d.allow
	d.reason == "resource_state_forbids_action"
}

test_auditor_may_not_write_notes if {
	d := authz.decision with input as act(
		alice(["auditor"]), "note.create", ticket_in_status("open"),
	)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

test_finance_approver_may_not_write_notes if {
	d := authz.decision with input as act(
		alice(["finance_approver"]), "note.create", ticket_in_status("open"),
	)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

test_note_create_denied_outside_tenant if {
	d := authz.decision with input as act(alice(["support_agent"]), "note.create", {
		"type": "ticket",
		"id": "TKT-3001",
		"organization_id": "22222222-2222-2222-2222-222222222222",
		"status": "open",
	})
	not d.allow
	d.reason == "not_a_member_of_resource_organization"
}

# Four arms again: exactly one must fire for any role and status.
test_note_create_has_exactly_one_decision_for_every_combination if {
	roles := [["support_agent"], ["support_manager"], ["auditor"], ["finance_approver"], []]
	statuses := ["open", "pending", "resolved", "closed"]
	every role in roles {
		every status in statuses {
			d := authz.decision with input as act(alice(role), "note.create", ticket_in_status(status))
			is_boolean(d.allow)
			is_string(d.reason)
		}
	}
}

# ================================================================================================
# Phase 4 — refund.propose and refund.approve
# ================================================================================================

refundable_order(status, currency, amount, requested) := {
	"type": "order",
	"id": "ORD-2001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"status": status,
	"currency": currency,
	"total_amount": amount,
	"requested_amount": requested,
	"requested_currency": currency,
}

pending_action(requester, expires) := {
	"type": "action_request",
	"id": "9c1f0000-0000-0000-0000-000000000001",
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"requester_id": requester,
	"expires_at": expires,
	"state": "PENDING_APPROVAL",
}

approve_ctx(now) := {"request_id": "req-a", "occurred_at": now, "network_zone": "internal"}

ALICE := "a1111111-1111-1111-1111-111111111111"
FIONA := "f1111111-1111-1111-1111-111111111111"

fiona(roles, level) := {
	"id": FIONA,
	"organizations": ["11111111-1111-1111-1111-111111111111"],
	"roles": roles,
	"authentication_level": level,
}

# --- refund.propose -----------------------------------------------------------------------------
test_agent_may_propose_within_role_limit if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("shipped", "USD", "149.90", "49.90"),
	)
	d.allow
	# Even a permitted proposal must go to approval. This obligation is the whole point.
	d.obligations.requires_approval == true
}

test_agent_denied_above_their_role_limit if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("shipped", "USD", "400.00", "250.00"),
	)
	not d.allow
	d.reason == "amount_exceeds_role_limit"
}

test_manager_allowed_where_agent_is_not if {
	d := authz.decision with input as act(
		alice(["support_manager"]), "refund.propose",
		refundable_order("shipped", "USD", "400.00", "250.00"),
	)
	d.allow
}

test_nobody_exceeds_the_action_maximum if {
	d := authz.decision with input as act(
		alice(["support_manager"]), "refund.propose",
		refundable_order("shipped", "USD", "900.00", "600.00"),
	)
	not d.allow
	d.reason == "amount_exceeds_action_maximum"
}

test_currency_must_match_the_order if {
	order := refundable_order("shipped", "USD", "149.90", "49.90")
	mismatched := object.union(order, {"requested_currency": "EUR"})
	d := authz.decision with input as act(alice(["support_agent"]), "refund.propose", mismatched)
	not d.allow
	d.reason == "currency_mismatch"
}

test_cancelled_order_cannot_be_refunded if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("cancelled", "USD", "149.90", "49.90"),
	)
	not d.allow
	d.reason == "resource_state_forbids_action"
}

test_already_refunded_order_cannot_be_refunded_again if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("refunded", "USD", "149.90", "49.90"),
	)
	not d.allow
	d.reason == "resource_state_forbids_action"
}

test_finance_approver_may_not_propose if {
	d := authz.decision with input as act(
		alice(["finance_approver"]), "refund.propose",
		refundable_order("shipped", "USD", "149.90", "49.90"),
	)
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

# Exactly at the limit is allowed; one cent over is not.
test_amount_exactly_at_the_role_limit_is_allowed if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("shipped", "USD", "300.00", "200.00"),
	)
	d.allow
}

test_one_cent_over_the_role_limit_is_denied if {
	d := authz.decision with input as act(
		alice(["support_agent"]), "refund.propose",
		refundable_order("shipped", "USD", "300.00", "200.01"),
	)
	not d.allow
	d.reason == "amount_exceeds_role_limit"
}

# --- refund.approve -----------------------------------------------------------------------------
test_independent_approver_with_mfa_may_approve if {
	d := authz.decision with input as {
		"subject": fiona(["finance_approver"], "mfa"),
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	}
	d.allow
	d.reason == "independent_approver_verified"
}

# The single most important test in the file.
test_requester_cannot_approve_their_own_action if {
	d := authz.decision with input as {
		"subject": {
			"id": ALICE,
			"organizations": ["11111111-1111-1111-1111-111111111111"],
			"roles": ["support_agent", "finance_approver"],
			"authentication_level": "mfa",
		},
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	}
	not d.allow
	d.reason == "self_approval_not_permitted"
}

test_non_approver_may_not_approve if {
	d := authz.decision with input as {
		"subject": fiona(["support_manager"], "mfa"),
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	}
	not d.allow
	d.reason == "role_not_permitted_for_action"
}

test_expired_approval_window_is_refused if {
	d := authz.decision with input as {
		"subject": fiona(["finance_approver"], "mfa"),
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-10-01T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	}
	not d.allow
	d.reason == "approval_expired"
}

# Production configuration: MFA required. Asserted with the data overridden, so this test states
# the production rule regardless of what the local bundle is set to.
test_single_factor_approver_is_refused_when_mfa_is_required if {
	d := authz.decision with input as {
		"subject": fiona(["finance_approver"], "single_factor"),
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	} with data.limits.refund.approval.require_mfa as true
	not d.allow
	d.reason == "authentication_level_insufficient"
}

test_mfa_approver_is_allowed_when_mfa_is_required if {
	d := authz.decision with input as {
		"subject": fiona(["finance_approver"], "mfa"),
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	} with data.limits.refund.approval.require_mfa as true
	d.allow
}

# Relaxing the factor requirement must not relax anything else. Self-approval stays refused even
# with MFA switched off, which is what stops AC-01 from quietly widening into a real hole.
test_self_approval_still_refused_when_mfa_is_not_required if {
	d := authz.decision with input as {
		"subject": {
			"id": ALICE,
			"organizations": ["11111111-1111-1111-1111-111111111111"],
			"roles": ["finance_approver"],
			"authentication_level": "single_factor",
		},
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2026-12-31T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	} with data.limits.refund.approval.require_mfa as false
	not d.allow
	d.reason == "self_approval_not_permitted"
}

# Self-approval is checked before everything else, so a requester learns nothing about the other
# conditions by attempting it.
test_self_approval_beats_every_other_reason if {
	d := authz.decision with input as {
		"subject": {
			"id": ALICE,
			"organizations": ["22222222-2222-2222-2222-222222222222"],
			"roles": [],
			"authentication_level": "single_factor",
		},
		"action": "refund.approve",
		"resource": pending_action(ALICE, "2020-01-01T00:00:00Z"),
		"context": approve_ctx("2026-10-08T10:00:00Z"),
	}
	not d.allow
	d.reason == "self_approval_not_permitted"
}
