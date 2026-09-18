# Policy contract

Normative for `policy/supportpilot/` and the API's OPA client. Derived from
[../docs/architecture/](../docs/architecture/#what-actually-decides).

## The contract in one sentence

The API sends a fully server-built input; OPA returns `allow`, a stable `reason`, a `policy_version`,
and optional `obligations`; the **API enforces the result**, and anything abnormal is a deny.

## Input

Built entirely from verified identity, server-side lookups, and infrastructure context. **No field in
this input may originate from a model argument.**

```json
{
  "input": {
    "subject": {
      "id": "alice-id",
      "organizations": ["cedar"],
      "roles": ["support_agent"],
      "authentication_level": "mfa"
    },
    "action": "order.read",
    "resource": {
      "type": "order",
      "id": "ORD-2001",
      "organization_id": "cedar",
      "status": "shipped",
      "currency": "USD",
      "total_amount": "149.90",
      "requester_id": null
    },
    "context": {
      "request_id": "req-123",
      "occurred_at": "2026-10-08T10:15:00Z",
      "network_zone": "internal"
    }
  }
}
```

| Field | Source | Never from |
|---|---|---|
| `subject.id` | Token `sub`, resolved to `app.users.id` | Request body |
| `subject.organizations`, `subject.roles` | `app.memberships` where `status='active'` | Token claims alone, model arguments |
| `action` | Server route → action mapping | Anything the caller sends |
| `resource.*` | Database lookup performed **before** the policy call | The request payload |
| `context.*` | Server clock and infrastructure | Client headers |

`resource.requester_id` is populated for approval actions so the policy can enforce separation of
duty without a second lookup.

## Output

```json
{
  "result": {
    "allow": true,
    "reason": "same_organization_and_allowed_role",
    "policy_version": "2026-09-07.1",
    "obligations": {
      "allowed_fields": ["order_number", "status", "currency", "total_amount"],
      "max_results": 20
    }
  }
}
```

| Key | Required | Meaning |
|---|---|---|
| `allow` | yes | Boolean. Anything not exactly `true` is a deny |
| `reason` | yes | Stable snake_case code, safe to log and to record in audit |
| `policy_version` | yes | Recorded on every decision and every audit row |
| `obligations.allowed_fields` | no | Whitelist; the API removes everything else before serializing |
| `obligations.max_results` | no | Caps pagination below the endpoint default |
| `obligations.requires_approval` | no | Action must enter `PENDING_APPROVAL` even if otherwise permitted |

## Actions

| Action | Resource type | Introduced |
|---|---|---|
| `order.read` | `order` | Phase 1 |
| `customer.search` | `organization` | Phase 2 |
| `customer.read` | `customer` | Phase 2 |
| `ticket.read` | `ticket` | Phase 2 |
| `note.create` | `ticket` | Phase 3 |
| `refund.propose` | `order` | Phase 4 |
| `refund.approve` | `action_request` | Phase 4 |
| `action.read` | `action_request` | Phase 4 |

## Reason codes

Stable. Renaming one is a control-plane change — dashboards and alerts key on these.

| Reason | Allow | Meaning |
|---|---|---|
| `default_deny` | no | No rule matched |
| `same_organization_and_allowed_role` | yes | Tenant and role satisfied |
| `not_a_member_of_resource_organization` | no | Cross-tenant attempt |
| `role_not_permitted_for_action` | no | In tenant, wrong role |
| `resource_state_forbids_action` | no | e.g. refund on a cancelled order |
| `amount_exceeds_role_limit` | no | Over the role's configured cap |
| `amount_exceeds_action_maximum` | no | Over `ACTION_MAX_AMOUNT` |
| `currency_mismatch` | no | Refund currency ≠ order currency |
| `self_approval_not_permitted` | no | Requester is the approver |
| `approval_expired` | no | Decision attempted after expiry |
| `authentication_level_insufficient` | no | MFA required for this action |
| `membership_inactive` | no | Membership revoked since the token was issued |

## Rules

```rego
package supportpilot.authz

import rego.v1

policy_version := "2026-09-07.1"

default decision := {
  "allow": false,
  "reason": "default_deny",
  "policy_version": policy_version
}

# --- helpers -----------------------------------------------------------

in_tenant if input.resource.organization_id in input.subject.organizations

has_role(r) if r in input.subject.roles

read_roles := {"support_agent", "support_manager", "auditor"}

# --- order.read --------------------------------------------------------

decision := allow_with("same_organization_and_allowed_role", {
  "allowed_fields": ["order_number", "status", "currency", "total_amount",
                     "placed_at", "updated_at"]
}) if {
  input.action == "order.read"
  in_tenant
  some r in read_roles
  has_role(r)
}

decision := deny("not_a_member_of_resource_organization") if {
  input.action == "order.read"
  not in_tenant
}

# --- refund.propose ----------------------------------------------------

decision := deny("resource_state_forbids_action") if {
  input.action == "refund.propose"
  input.resource.status in {"cancelled", "refunded"}
}

decision := deny("currency_mismatch") if {
  input.action == "refund.propose"
  input.resource.currency != input.context.requested_currency
}

decision := deny("amount_exceeds_role_limit") if {
  input.action == "refund.propose"
  to_number(input.context.requested_amount) > role_limit
}

decision := allow_with("same_organization_and_allowed_role", {
  "requires_approval": true
}) if {
  input.action == "refund.propose"
  in_tenant
  has_role("support_agent")
  input.resource.status in {"paid", "shipped", "delivered"}
  to_number(input.context.requested_amount) <= role_limit
}

# --- refund.approve ----------------------------------------------------

decision := deny("self_approval_not_permitted") if {
  input.action == "refund.approve"
  input.subject.id == input.resource.requester_id
}

decision := deny("approval_expired") if {
  input.action == "refund.approve"
  time.parse_rfc3339_ns(input.context.occurred_at) >
    time.parse_rfc3339_ns(input.resource.expires_at)
}

decision := allow_with("same_organization_and_allowed_role", {}) if {
  input.action == "refund.approve"
  in_tenant
  has_role("finance_approver")
  input.subject.id != input.resource.requester_id
  input.subject.authentication_level == "mfa"
}

# --- constructors ------------------------------------------------------

allow_with(reason, obligations) := {
  "allow": true, "reason": reason,
  "policy_version": policy_version, "obligations": obligations
}

deny(reason) := {
  "allow": false, "reason": reason, "policy_version": policy_version
}
```

`role_limit` comes from versioned policy **data**, not from a request or an environment variable read
at runtime:

```json
{ "limits": { "support_agent": 200.00, "support_manager": 500.00 } }
```

> **Rule-order note:** deny rules for a given action are written so they cannot be true at the same
> time as that action's allow rule — an ambiguous `decision` is a conflict error in Rego, and the API
> treats an error as deny. Policy tests assert exactly one decision per input.

## API-side enforcement

The client is as important as the policy. It must:

1. Send the input over the private `policy` network only.
2. Apply a short timeout (250 ms suggested; configurable, never unbounded).
3. Treat **every** abnormal outcome as deny: timeout, connection error, non-200, missing `result`,
   `allow` absent or not boolean `true`, missing `reason`, missing `policy_version`, conflict error.
4. Never cache an allow. A short negative cache is acceptable; a positive cache is not.
5. Record `reason` and `policy_version` on the decision log and the audit row.
6. Apply `obligations.allowed_fields` **before** serialization and before anything is logged.
7. Never retry a deny with modified input.

```
OPA unreachable        → 503 unavailable, audit decision=denied reason=policy_unavailable
OPA 200, allow=false   → 404/403 per the API contract, audit decision=denied reason=<policy reason>
OPA 200, malformed     → 503 unavailable, audit decision=denied reason=policy_malformed
```

## Tests (`policy/tests/`)

Policy tests run before a bundle may be published. Required coverage:

- Every action × every role, in tenant and out of tenant.
- Default deny for an unknown action and an unknown role.
- Each deny reason produced by at least one case.
- Obligations asserted field-by-field, not just presence.
- Exactly one decision per input — no ambiguity.
- Boundary cases: amount exactly at the limit, one cent over; expiry exactly at the timestamp.
- Separation of duty: requester ≠ approver, and requester = approver.

```rego
package supportpilot.authz_test

import rego.v1
import data.supportpilot.authz

test_agent_reads_own_tenant_order if {
  d := authz.decision with input as {
    "subject": {"id": "alice", "organizations": ["cedar"], "roles": ["support_agent"]},
    "action": "order.read",
    "resource": {"type": "order", "id": "ORD-2001", "organization_id": "cedar"}
  }
  d.allow
  d.reason == "same_organization_and_allowed_role"
}

test_agent_cannot_read_other_tenant_order if {
  d := authz.decision with input as {
    "subject": {"id": "alice", "organizations": ["cedar"], "roles": ["support_agent"]},
    "action": "order.read",
    "resource": {"type": "order", "id": "ORD-3001", "organization_id": "northwind"}
  }
  not d.allow
  d.reason == "not_a_member_of_resource_organization"
}

test_requester_cannot_approve_own_refund if {
  d := authz.decision with input as {
    "subject": {"id": "alice", "organizations": ["cedar"],
                "roles": ["support_agent", "finance_approver"],
                "authentication_level": "mfa"},
    "action": "refund.approve",
    "resource": {"type": "action_request", "organization_id": "cedar", "requester_id": "alice"}
  }
  not d.allow
  d.reason == "self_approval_not_permitted"
}
```

The third test is the one that matters most: alice holds **both** roles and is still refused, because
separation of duty lives in policy rather than in the portal (`R-13`, `T-010`).

## Publication

- The bundle is mounted read-only; OPA never writes policy.
- Only the control-plane deployment identity may publish a new bundle.
- `policy_version` is bumped on every publication and recorded in the release evidence.
- A bundle whose tests do not pass cannot be published.
