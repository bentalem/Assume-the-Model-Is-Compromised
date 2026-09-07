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
