# SupportPilot authorization policy.
#
# The API builds `input` entirely from verified identity and server-side lookups. Nothing here may
# be reached by a model argument. The API enforces the returned decision; anything abnormal —
# undefined, malformed, timed out, unreachable — is a deny on the API side (SP-DATA-001 §3).

package supportpilot.authz

import rego.v1

policy_version := "2026-09-07.1"

# Liveness probe target. Carries no authorization meaning.
health := {"status": "ok", "policy_version": policy_version}

# ------------------------------------------------------------------------------------------------
# Default deny. Every allow below must state its own reason.
#
# The version is written out literally because a default rule value may not reference a variable.
# `test_default_deny_version_matches_constant` fails if this drifts from `policy_version`.
# ------------------------------------------------------------------------------------------------
default decision := {
	"allow": false,
	"reason": "default_deny",
	"policy_version": "2026-09-07.1",
}

# ------------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------------
in_tenant if input.resource.organization_id in input.subject.organizations

has_role(r) if r in input.subject.roles

any_role(rs) if {
	some r in rs
	has_role(r)
}

read_roles := {"support_agent", "support_manager", "auditor"}

order_fields := [
	"order_number", "status", "currency", "total_amount",
	"placed_at", "updated_at", "items", "shipment",
]

# A normal customer record. Note what is absent: no internal identifier, no organization.
customer_fields := [
	"customer_ref", "full_name", "email", "assigned_team", "open_ticket_count",
]

# A customer marked `restricted` loses the contact details. The obligation is how that happens —
# the API removes the fields, and the response model never sees them.
customer_fields_restricted := [
	"customer_ref", "full_name", "assigned_team", "open_ticket_count",
]

search_fields := ["customer_ref", "full_name", "assigned_team"]

ticket_fields := [
	"ticket_number", "subject", "status", "assigned_team",
	"customer_ref", "created_at", "updated_at", "messages",
]

allow_with(reason, obligations) := {
	"allow": true,
	"reason": reason,
	"policy_version": policy_version,
	"obligations": obligations,
}

deny(reason) := {
	"allow": false,
	"reason": reason,
	"policy_version": policy_version,
}

# ------------------------------------------------------------------------------------------------
# order.read
#
# Deny arms are written so that at most one arm — allow or a single deny — is true for any input.
# An ambiguous `decision` is a conflict error in Rego, and the API treats an error as deny, but the
# policy tests assert exactly one decision so ambiguity is caught before publication.
# ------------------------------------------------------------------------------------------------
decision := allow_with("same_organization_and_allowed_role", {"allowed_fields": order_fields}) if {
	input.action == "order.read"
	in_tenant
	any_role(read_roles)
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "order.read"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "order.read"
	in_tenant
	not any_role(read_roles)
}

# ------------------------------------------------------------------------------------------------
# customer.search
#
# Searching is bounded by an obligation rather than by trusting the caller's page size, so a policy
# change can tighten every search tool at once without touching application code.
# ------------------------------------------------------------------------------------------------
decision := allow_with("same_organization_and_allowed_role", {
	"allowed_fields": search_fields,
	"max_results": 25,
}) if {
	input.action == "customer.search"
	in_tenant
	any_role(read_roles)
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "customer.search"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "customer.search"
	in_tenant
	not any_role(read_roles)
}

# ------------------------------------------------------------------------------------------------
# customer.read
#
# Sensitivity narrows the field set. A support_agent reading a restricted customer still gets an
# answer — without contact details. Managers and auditors see the full record.
# ------------------------------------------------------------------------------------------------
decision := allow_with("restricted_customer_minimal_fields", {
	"allowed_fields": customer_fields_restricted,
}) if {
	input.action == "customer.read"
	in_tenant
	any_role(read_roles)
	input.resource.sensitivity == "restricted"
	not any_role({"support_manager", "auditor"})
}

decision := allow_with("same_organization_and_allowed_role", {
	"allowed_fields": customer_fields,
}) if {
	input.action == "customer.read"
	in_tenant
	any_role(read_roles)
	input.resource.sensitivity != "restricted"
}

decision := allow_with("same_organization_and_allowed_role", {
	"allowed_fields": customer_fields,
}) if {
	input.action == "customer.read"
	in_tenant
	input.resource.sensitivity == "restricted"
	any_role({"support_manager", "auditor"})
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "customer.read"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "customer.read"
	in_tenant
	not any_role(read_roles)
}

# ------------------------------------------------------------------------------------------------
# ticket.read
#
# Restricted *messages* are filtered by the database row policy, not here. This decides access to
# the ticket; the database decides which messages within it are visible. Two layers, each doing the
# part it is best placed to enforce.
# ------------------------------------------------------------------------------------------------
decision := allow_with("same_organization_and_allowed_role", {
	"allowed_fields": ticket_fields,
	"max_results": 50,
}) if {
	input.action == "ticket.read"
	in_tenant
	any_role(read_roles)
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "ticket.read"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "ticket.read"
	in_tenant
	not any_role(read_roles)
}

# ------------------------------------------------------------------------------------------------
# note.create
#
# A closed ticket does not take new notes: the record of a closed case should not keep changing.
# That is a business rule, so it lives here rather than in application code, and the deny arm names
# the reason so the audit trail explains itself.
# ------------------------------------------------------------------------------------------------
note_authors := {"support_agent", "support_manager"}

decision := allow_with("same_organization_and_allowed_role", {}) if {
	input.action == "note.create"
	in_tenant
	any_role(note_authors)
	input.resource.status != "closed"
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "note.create"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "note.create"
	in_tenant
	not any_role(note_authors)
}

decision := deny("resource_state_forbids_action") if {
	input.action == "note.create"
	in_tenant
	any_role(note_authors)
	input.resource.status == "closed"
}

# ------------------------------------------------------------------------------------------------
# refund.propose
#
# Limits come from versioned policy data (limits.json), not from an environment variable read at
# runtime. A limit change is then a reviewed policy publication with a version, which is what
# SP-OPS-001 §10 requires of it.
# ------------------------------------------------------------------------------------------------
# data.limits, not data.supportpilot.limits: OPA maps a JSON file to a path from the *bundle root*,
# and limits.json sits at the root of the mounted bundle. Nesting it to match the package name would
# mean a supportpilot/ directory inside the bundle, which buys nothing.
refund_limits := data.limits.refund

# The lowest limit the caller's roles allow. A user holding two roles gets the *higher* of their
# own limits, but never more than the action maximum.
role_limit := limit if {
	limits := {l |
		some role in input.subject.roles
		l := refund_limits.per_role[role]
	}
	count(limits) > 0
	limit := min([max(limits), refund_limits.action_maximum])
}

requested_amount := to_number(input.resource.requested_amount)

refundable_states := {"paid", "shipped", "delivered"}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "refund.propose"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "refund.propose"
	in_tenant
	not any_role({"support_agent", "support_manager"})
}

decision := deny("resource_state_forbids_action") if {
	input.action == "refund.propose"
	in_tenant
	any_role({"support_agent", "support_manager"})
	not input.resource.status in refundable_states
}

decision := deny("currency_mismatch") if {
	input.action == "refund.propose"
	in_tenant
	any_role({"support_agent", "support_manager"})
	input.resource.status in refundable_states
	input.resource.requested_currency != input.resource.currency
}

decision := deny("amount_exceeds_action_maximum") if {
	input.action == "refund.propose"
	in_tenant
	any_role({"support_agent", "support_manager"})
	input.resource.status in refundable_states
	input.resource.requested_currency == input.resource.currency
	requested_amount > refund_limits.action_maximum
}

decision := deny("amount_exceeds_role_limit") if {
	input.action == "refund.propose"
	in_tenant
	any_role({"support_agent", "support_manager"})
	input.resource.status in refundable_states
	input.resource.requested_currency == input.resource.currency
	requested_amount <= refund_limits.action_maximum
	requested_amount > role_limit
}

# The only allow arm. Note the obligation: even a permitted proposal must go to approval.
decision := allow_with("same_organization_and_allowed_role", {
	"requires_approval": true,
}) if {
	input.action == "refund.propose"
	in_tenant
	any_role({"support_agent", "support_manager"})
	input.resource.status in refundable_states
	input.resource.requested_currency == input.resource.currency
	requested_amount <= role_limit
	requested_amount <= refund_limits.action_maximum
}

# ------------------------------------------------------------------------------------------------
# refund.approve
#
# Separation of duty lives here, in policy — not only in the approval portal, and not only in the
# database trigger. All three refuse it, which is the point: no single mistake re-enables it.
# ------------------------------------------------------------------------------------------------
decision := deny("self_approval_not_permitted") if {
	input.action == "refund.approve"
	input.subject.id == input.resource.requester_id
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "refund.approve"
	input.subject.id != input.resource.requester_id
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "refund.approve"
	input.subject.id != input.resource.requester_id
	in_tenant
	not has_role("finance_approver")
}

decision := deny("approval_expired") if {
	input.action == "refund.approve"
	input.subject.id != input.resource.requester_id
	in_tenant
	has_role("finance_approver")
	time.parse_rfc3339_ns(input.context.occurred_at) > time.parse_rfc3339_ns(input.resource.expires_at)
}

# Whether approval requires multi-factor is versioned policy data, not a constant. It is false in
# the local bundle (AC-01: the local realm cannot enforce MFA) and must be true in production. That
# keeps the requirement visible and reviewable instead of being deleted to make a demo work.
approval_requires_mfa if refund_limits.approval.require_mfa

approver_authentication_sufficient if not approval_requires_mfa

approver_authentication_sufficient if {
	approval_requires_mfa
	input.subject.authentication_level == "mfa"
}

decision := deny("authentication_level_insufficient") if {
	input.action == "refund.approve"
	input.subject.id != input.resource.requester_id
	in_tenant
	has_role("finance_approver")
	time.parse_rfc3339_ns(input.context.occurred_at) <= time.parse_rfc3339_ns(input.resource.expires_at)
	not approver_authentication_sufficient
}

decision := allow_with("independent_approver_verified", {}) if {
	input.action == "refund.approve"
	input.subject.id != input.resource.requester_id
	in_tenant
	has_role("finance_approver")
	time.parse_rfc3339_ns(input.context.occurred_at) <= time.parse_rfc3339_ns(input.resource.expires_at)
	approver_authentication_sufficient
}

# ------------------------------------------------------------------------------------------------
# action.read
# ------------------------------------------------------------------------------------------------
decision := allow_with("same_organization_and_allowed_role", {}) if {
	input.action == "action.read"
	in_tenant
	any_role({"support_agent", "support_manager", "finance_approver", "auditor"})
}

decision := deny("not_a_member_of_resource_organization") if {
	input.action == "action.read"
	not in_tenant
}

decision := deny("role_not_permitted_for_action") if {
	input.action == "action.read"
	in_tenant
	not any_role({"support_agent", "support_manager", "finance_approver", "auditor"})
}
