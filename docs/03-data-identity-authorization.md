# 03 — Data, identity, and authorization

> Source: `03_SupportPilot_Data_Identity_and_Authorization.docx` (SP-DATA-001 v1.0, 2026-09-07)
> Implementation detail lives in [../specs/database-schema.md](../specs/database-schema.md) and
> [../specs/policy-contract.md](../specs/policy-contract.md).

## 1. Identity model

Keycloak is the identity authority. Each human uses an individual account. Each runtime service uses
a separate workload identity. Administrative work uses separate privileged accounts.

| Identity | Used by | Purpose |
|---|---|---|
| Human user token | Onyx and API | Current person, session, memberships, approved scopes |
| Onyx workload identity | Onyx | Calls approved platform services |
| API workload identity | API | Reads secrets, reaches OPA and PostgreSQL |
| Worker workload identity | Worker | Claims approved jobs, reaches allowlisted providers |
| Deployment identity | CI/CD | Deploys reviewed service versions |
| Migration identity | Migration job | Changes schema, grants, row policies |
| Administrator identity | Authorized operator | Approved control-plane administration |

**Identity rule:** a chat statement such as "I am an administrator" has no effect. Only verified
identity and server-side authorization data are used.

## 2. Token handling

1. The user authenticates with Keycloak and completes required MFA.
2. Onyx receives a user-bound access token through the configured OAuth flow.
3. Onyx sends the access token to the API when invoking an action.
4. The API verifies signature, issuer, audience, expiry, and required claims.
5. The API uses the subject identifier to load **current** membership and resource attributes.
6. The API constructs policy input. It does not trust organization, role, or approval fields supplied
   by the model.

### Required token checks

- Expected issuer exactly matches the configured Keycloak realm.
- Audience includes the SupportPilot API.
- Signature uses an allowed algorithm and a current trusted key.
- Expiration and not-before enforced with limited clock tolerance.
- Token type and authorized party checked according to the selected flow.
- Scopes map to actions but **do not replace resource-level authorization**.

## 3. Authorization model

Each decision uses four attribute groups:

| Group | Examples | Trusted source |
|---|---|---|
| Subject | User id, organization memberships, support role | Verified token and server-side membership data |
| Action | `order.read`, `note.create`, `refund.propose`, `refund.approve` | Server route and tool mapping |
| Resource | Order organization, owner, status, amount, currency | Database lookup **before** policy evaluation |
| Context | Request time, authentication strength, action risk, network zone | Trusted server and infrastructure data |

OPA returns a decision; the API enforces it. A response includes `allow`, a reason code, a policy
version, and any obligations such as field filtering or required approval.

**Failure rule:** undefined, malformed, unavailable, or timed-out policy responses are **deny** for
protected operations.

## 4. OPA contract

Request:

```json
{
  "input": {
    "subject": { "id": "alice-id", "organizations": ["cedar"], "roles": ["support_agent"] },
    "action": "order.read",
    "resource": { "type": "order", "id": "ORD-2001", "organization_id": "cedar" },
    "context": { "request_id": "req-123", "authentication_level": "mfa" }
  }
}
```

Response:

```json
{
  "result": {
    "allow": true,
    "reason": "same_organization_and_allowed_role",
    "policy_version": "2026-09-07.1",
    "obligations": { "allowed_fields": ["order_number", "status", "total_amount"] }
  }
}
```

Full rule set and reason codes: [../specs/policy-contract.md](../specs/policy-contract.md).

## 5. Database roles

| Role | Used by | Permissions |
|---|---|---|
| `sp_api_role` | API | Connect; use runtime schema; select approved views/tables; insert allowed requests and notes; **no schema administration** |
| `sp_worker_role` | Worker | Read and claim approved jobs; update execution state; call only approved functions |
| `sp_migrator_role` | Migration job | Own schemas; apply versioned schema, grants, indexes, RLS policies |
| `sp_auditor_role` | Approved audit tooling | Read audit views; no business writes |
| `postgres_admin` | Emergency operator | Administrative access under controlled procedures; **never mounted into runtime containers** |

### Runtime role restrictions

- No `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, or `BYPASSRLS`.
- Runtime roles do not own protected tables.
- Public schema creation is revoked where applicable.
- Default privileges are explicitly controlled for new tables and functions.
- Database access allowed only from expected service networks.
- Every connection sets a clear `application_name` for monitoring.

## 6. Data model

| Table | Purpose | Key security fields |
|---|---|---|
| `organizations` | Tenant root | `id`, `status` |
| `users` | Application identity reference | `id`, `identity_subject`, `status` |
| `memberships` | User-to-organization role assignment | `user_id`, `organization_id`, `role`, `status` |
| `customers` | Customer record | `organization_id`, `assigned_team`, `sensitivity` |
| `orders` | Order summary | `organization_id`, `customer_id`, `status`, `currency`, `total_amount` |
| `order_items` | Line items | `organization_id`, `order_id` |
| `shipments` | Shipment state and tracking | `organization_id`, `order_id` |
| `tickets` | Support case | `organization_id`, `customer_id`, `assigned_team`, `status` |
| `ticket_messages` | Conversation entries | `organization_id`, `ticket_id`, `visibility` |
| `internal_notes` | Staff-only notes | `organization_id`, `ticket_id`, `author_id` |
| `action_requests` | Proposed sensitive actions | `organization_id`, `requester_id`, `action_type`, `payload_hash`, `state` |
| `approval_decisions` | Independent decisions | `action_request_id`, `approver_id`, `decision`, `policy_version` |
| `action_jobs` | Worker queue | `action_request_id`, `state`, `attempts`, `lease` |
| `action_executions` | Execution evidence | `job_id`, `idempotency_key`, `provider_reference`, `outcome` |
| `audit_events` | Security and business evidence | `actor`, `action`, `resource`, `decision`, `request_id`, `event_hash` |

DDL: [../specs/database-schema.md](../specs/database-schema.md).

## 7. Row security

Protected tables contain `organization_id`. The API starts a transaction and sets trusted request
context **locally**, so pooled connections do not retain one user's identity for the next request.

```sql
BEGIN;
SET LOCAL app.user_id         = 'alice-id';
SET LOCAL app.organization_id = 'cedar';

SELECT order_number, status, total_amount
FROM app.orders
WHERE order_number = $1;

COMMIT;
```

```sql
ALTER TABLE app.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.orders FORCE  ROW LEVEL SECURITY;

CREATE POLICY orders_tenant_read
ON app.orders
FOR SELECT
TO sp_api_role
USING (organization_id = current_setting('app.organization_id', true)::uuid);
```

- The application role **must not own the table** — owners normally bypass row policies.
- The application role must not have `BYPASSRLS`.
- Missing request context must result in no visible rows or a controlled error.
- Policies for `SELECT`, `INSERT`, `UPDATE`, `DELETE` are defined separately when rules differ.
- Policy tests cover every protected table and every runtime role.

## 8. Query rules

- The model selects a business tool; it never supplies SQL.
- Each tool maps to reviewed code and parameterized statements.
- Identifiers are validated for syntax and length before database use.
- Queries select named columns, never `SELECT *`.
- Pagination and maximum result sizes are mandatory for list and search tools.
- Write statements include expected current state to prevent stale updates.
- Transactions group business state and required audit evidence.
- Database errors map to stable API errors without returning schema details.

## 9. Audit model

| Field | Purpose |
|---|---|
| `event_id` | Unique event identifier |
| `occurred_at` | Trusted server timestamp |
| `request_id` / `trace_id` | Connect events across Onyx, API, OPA, database, worker, provider |
| `actor_type` / `actor_id` | Human or workload identity responsible |
| `organization_id` | Tenant context |
| `action` | Normalized operation, e.g. `order.read`, `refund.execute` |
| `resource_type` / `resource_id` | Target business object |
| `decision` / `reason` | Allowed, denied, approved, rejected, succeeded, failed + stable reason |
| `policy_version` | Policy version used for the decision |
| `payload_hash` | Integrity binding for sensitive action parameters |
| `result_reference` | Provider or execution reference, without sensitive response bodies |
| `previous_event_hash` / `event_hash` | Optional chain for tamper evidence |

Prompts and complete model conversations are **not** automatically audit evidence. Store them only
when a defined purpose, access policy, retention period, and redaction process exist (OD-08).

## 10. Secrets

| Secret | Consumer | Handling |
|---|---|---|
| Model provider API key | Onyx | Mounted only into the Onyx model-provider service; never returned to users or tools |
| Database API credential | API | Mounted only into the API container; rotated independently |
| Database worker credential | Worker | Mounted only into the worker container |
| Migration credential | Migration job | Available only during deployment; removed after the job exits |
| OAuth client secret | Onyx or backend OAuth client | Appropriate secret store; **not** in agent instructions |
| Provider credential | Worker | Scoped to approved operations and destinations; short-lived when supported |

## 11. Acceptance checks

- [ ] Tokens with wrong issuer, audience, signature, expiry, or algorithm are rejected.
- [ ] Changing tool arguments cannot change the verified user or organization.
- [ ] Every cross-tenant read returns no protected data at API **and** database layers.
- [ ] The API database role cannot alter schemas, grants, policies, or roles.
- [ ] The worker database role cannot read broad customer data.
- [ ] A pooled database connection does not retain previous request context.
- [ ] OPA default behavior is deny and its unavailability blocks protected operations.
- [ ] Logs and model context contain no database, OAuth, model-provider, or payment-provider secrets.
