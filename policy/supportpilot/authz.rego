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
	"placed_at", "updated_at",
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
