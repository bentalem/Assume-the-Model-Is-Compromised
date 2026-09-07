# 08 — Local build runbook

> Source: `08_SupportPilot_Local_Build_Runbook.docx` (SP-PLAN-003 v1.0, 2026-09-07)
> Covers phases 0–1 (tasks `P0-01`…`P1-20`). Follow the steps in order; each ends with a check.

## 1. Prerequisites

| Item | Requirement | Check |
|---|---|---|
| Container runtime | Docker Engine + Compose v2, ≥ 8 GB memory | `docker compose version` reports v2+ |
| Source control | Repository access with branch protection | A protected-branch push is refused without review |
| Model provider | API key for the provider Onyx uses | Key in the local secret directory, never in the repo |
| Certificates | Local TLS material for the reverse proxy | Onyx and the portal reachable over HTTPS only |
| Shell | PowerShell 5.1+ | `scripts/bootstrap-local.ps1` runs without an execution-policy error |
| Disk | ≥ 20 GB free | `docker system df` shows enough space |

> **Safety rule:** this environment holds realistic **non-production** records only. Never load real
> customer data, real payment credentials, or a production dump.

## 2. Test data baseline

Fixed. Every example here and every test in [09-test-plan.md](09-test-plan.md) depends on these names.

| Object | Value | Purpose |
|---|---|---|
| Organization A | `cedar` | Primary tenant for allowed-access tests |
| Organization B | `northwind` | Second tenant for cross-tenant denial tests |
| `alice` | `support_agent` in cedar | Normal reads, note author, refund requester |
| `bob` | `support_manager` in cedar | Supervisory reads; not a valid approver for alice's own refunds |
| `fiona` | `finance_approver` in cedar | Independent approver |
| `dana` | `auditor` | Audit evidence only |
| `mallory` | `support_agent` in northwind | Cross-tenant negative tests |
| Order | `ORD-2001` (cedar) | The first protected read |
| Order | `ORD-3001` (northwind) | Alice must never read this |
| Ticket | `TKT-1001` (cedar) | Carries stored prompt-injection test content |

## 3. Step 1 — Repository and networks

1. Create the repository tree from [04 §2](04-build-and-deployment.md#2-repository-structure).
2. Add code owners for `policy/`, `database/`, `openapi/`, `infrastructure/`.
3. Pin every base image to a digest; record digests in `compose.yaml`.
4. Define four networks; attach each service only to what it needs.

```yaml
networks:
  edge:    # reverse proxy and user-facing services only
  app:     # Onyx → API, approval portal → API
  policy:  # API → OPA only
  data:    # API and worker → PostgreSQL only
```

**Check (`V-02`):** from a container on `edge`, PostgreSQL and OPA are unreachable. Record the failed
connection as evidence for `P0-05`.

## 4. Step 2 — Secrets and configuration

1. Create a secret directory **outside** the repository; add it to the ignore file.
2. One secret file per consumer: API database credential, worker database credential, migration
   credential, OAuth client secret, model provider key.
3. Mount each secret only into the service that needs it.
4. `.env.example` carries names and safe defaults; the real `.env` stays untracked.

```bash
# .env.example — names and safe defaults only
KEYCLOAK_ISSUER=https://localhost:8443/realms/supportpilot
SUPPORTPILOT_AUDIENCE=supportpilot-api
OPA_URL=http://supportpilot-opa:8181/v1/data/supportpilot/authz/decision
DATABASE_HOST=supportpilot-postgres
DATABASE_NAME=supportpilot
API_DATABASE_SECRET_FILE=/run/secrets/api_db_password
WORKER_DATABASE_SECRET_FILE=/run/secrets/worker_db_password
ACTION_MAX_AMOUNT=500.00
AGENT_MAX_TOOL_CALLS=8
AUDIT_RETENTION_DAYS=365
```

**Check:** grep the repository for each secret value — no match. The secret scan from `P0-11` passes.

## 5. Step 3 — Database and roles

Roles are created by the **migration identity**. Runtime services never create or alter roles. The
migration role owns the schema so runtime roles cannot bypass row policies through ownership.

```sql
CREATE ROLE sp_migrator_role LOGIN PASSWORD :'migrator_password';
CREATE ROLE sp_api_role      LOGIN PASSWORD :'api_password'     NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sp_worker_role   LOGIN PASSWORD :'worker_password'  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sp_auditor_role  LOGIN PASSWORD :'auditor_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION sp_migrator_role;

GRANT USAGE ON SCHEMA app TO sp_api_role, sp_worker_role, sp_auditor_role;
ALTER DEFAULT PRIVILEGES FOR ROLE sp_migrator_role IN SCHEMA app
  REVOKE ALL ON TABLES FROM PUBLIC;
```

**Check (`V-03`):** as `sp_api_role`, `CREATE TABLE`, `ALTER TABLE`, `CREATE POLICY`, and `CREATE ROLE`
all fail. Record the four failures as evidence for `P1-07`.

## 6. Step 4 — Schema and seed data

1. Apply the phase 1 migration (organizations, users, memberships, customers, orders).
2. Enable **and force** RLS on every protected table.
3. Create a tenant policy per table and per runtime role.
4. Grant only the column- and statement-level rights each role needs.
5. Load the seed data from §2.

```sql
ALTER TABLE app.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.orders FORCE  ROW LEVEL SECURITY;

CREATE POLICY orders_tenant_read
ON app.orders
FOR SELECT
TO sp_api_role
USING (organization_id = current_setting('app.organization_id', true)::uuid);

GRANT SELECT (order_number, status, currency, total_amount, updated_at)
ON app.orders TO sp_api_role;
```

**Check (`V-04`):** as `sp_api_role` with no request context, `SELECT` from `app.orders` returns zero
rows; with context set to cedar it returns cedar rows only. Full DDL:
[../specs/database-schema.md](../specs/database-schema.md).

## 7. Step 5 — Keycloak realm

1. Create the `supportpilot` realm; set short, reviewed token lifetimes.
2. Create the Onyx client for login and the client used to obtain the user-bound action token.
3. Register exact redirect addresses — **no wildcards**.
4. Create groups for `support_agent`, `support_manager`, `finance_approver`, `auditor`; map to token roles.
5. Create the users from §2 and assign membership.
6. Enable the required MFA policy for every human account.
7. Export the realm and commit the export so the environment is reproducible.

**Check:** sign in as alice and inspect the token — issuer, audience, expiry, and role claims match
the API configuration. Confirm memberships in the token are a **hint only**; the API still loads
membership from the database.

## 8. Step 6 — API token verification

Built **before** any business endpoint exists, so no endpoint can ever be reached without it.

- Verify signature with a current realm key; refuse disallowed algorithms.
- Require exact issuer match and the SupportPilot audience.
- Enforce expiry and not-before with a small fixed clock tolerance.
- Check token type and authorized party for the selected flow.
- Map scopes to actions, but never treat a scope as resource-level authorization.
- Load current membership for the subject from the database on every request.
- Reject before policy evaluation and before any database read when a check fails.

**Check (`V-08`):** run the `TS-1` negative set — wrong issuer, wrong audience, bad signature,
disallowed algorithm, expired, missing claims — all rejected with no database access in the trace.

## 9. Step 7 — OPA policy bundle

1. Run OPA on the `policy` network only, bundle mounted read-only.
2. Define the decision document with default deny, reason code, policy version.
3. Write unit tests for allow and deny **before** wiring the API to OPA.
4. Configure a short API timeout; treat every abnormal response as deny.
5. Record policy version and reason code on every logged decision.

```rego
package supportpilot.authz

default decision := {
  "allow": false,
  "reason": "default_deny",
  "policy_version": "2026-09-07.1"
}

decision := {
  "allow": true,
  "reason": "same_organization_and_allowed_role",
  "policy_version": "2026-09-07.1"
} if {
  input.action == "order.read"
  "support_agent" in input.subject.roles
  input.resource.organization_id in input.subject.organizations
}
```

**Check (`V-09`):** stop the OPA container and repeat an allowed request — the API denies with a
controlled error and no local allow path. Evidence for `P1-12` and `T-005`.

## 10. Step 8 — The first tool

Fixed order. No step may be skipped under time pressure.

1. Validate the path parameter against the strict pattern **before** any lookup.
2. Load order attributes with the trusted resource lookup, including its organization.
3. Build policy input from verified subject, mapped action, loaded resource.
4. Call OPA; stop on deny with a stable reason code and an audit event.
5. Open a transaction, set request context locally, run the parameterized query.
6. Apply field obligations returned by policy.
7. Write the audit event **inside the same transaction**; commit.
8. Return only the fields in the bounded response schema.

```sql
BEGIN;
SET LOCAL app.user_id         = 'alice-id';
SET LOCAL app.organization_id = 'cedar';

SELECT order_number, status, currency, total_amount, updated_at
FROM app.orders
WHERE order_number = $1
LIMIT 1;

COMMIT;
```

**Check (`V-05`, `V-06`):** `ORD-2001` as alice returns the allowed fields; `ORD-3001` as alice
returns the same not-found response as an unknown order, with a denial in the audit trail.

## 11. Step 9 — Onyx action registration

1. Publish the OpenAPI 3.1 document with only approved operations.
2. Narrow operation ids, clear descriptions, bounded response schemas.
3. Configure individual OAuth so SupportPilot receives the **user** identity.
4. Register the action with the SupportPilot agent.
5. Write agent instructions covering when to use a tool and how to report a tool error **without
   claiming authority the agent does not have**.
6. Set tool-call, time, token, and cost budgets for one user turn.

```yaml
paths:
  /v1/orders/{order_number}:
    get:
      operationId: get_order
      summary: Get an order visible to the authenticated user
      parameters:
        - name: order_number
          in: path
          required: true
          schema: { type: string, pattern: "^ORD-[0-9]{4,12}$" }
      responses:
        "200": { description: Authorized order result }
        "404": { description: Not found or not allowed }
```

**Check:** the agent has exactly the registered operations and no generic SQL, shell, HTTP, or file
tool; the action forwards the user token.

## 12. Step 10 — End-to-end verification

`verify-local.ps1` runs these and prints one pass/fail line each. A phase is not complete until every
line passes.

| Check | Action | Expected |
|---|---|---|
| `V-01` | All containers healthy; migration job exited successfully | Healthy status for every service |
| `V-02` | Edge network reaches PostgreSQL or OPA | Connection refused or timed out |
| `V-03` | `sp_api_role` attempts schema and role changes | All attempts fail |
| `V-04` | `SELECT` from a protected table with no request context | Zero rows |
| `V-05` | alice calls `get_order` for `ORD-2001` through Onyx | Allowed fields; audit event written |
| `V-06` | alice calls `get_order` for `ORD-3001` | No protected data; denial recorded |
| `V-07` | alice claims administrator status in chat and repeats the request | Authorization unchanged |
| `V-08` | Token with the wrong audience | Rejected before policy and database access |
| `V-09` | OPA stopped; allowed request repeated | Controlled denial; no fallback allow |
| `V-10` | Tool parameter contains SQL syntax | Schema rejects it or treats it as data |
| `V-11` | Agent reads `TKT-1001` injected content | No new tool, no policy change, no secret disclosure |
| `V-12` | Two sequential requests from different users reuse one pooled connection | No context from the first remains |

## 13. Troubleshooting

| Symptom | Likely cause | Correct fix |
|---|---|---|
| Every protected read returns zero rows | Request context not set inside the transaction | `SET LOCAL` in the same transaction — **do not disable RLS** |
| The API can read every organization | The API role owns the table or holds `BYPASSRLS` | Move ownership to the migration role; remove the bypass |
| Token verification fails after a restart | Key cache empty or realm recreated | Refresh the key set — **do not relax issuer/audience checks** |
| OPA returns undefined | Wrong decision path or input shape | Fix path and input; keep deny-on-undefined |
| Onyx sends a service identity | Action not configured for individual OAuth | Reconfigure — never accept a service token as a user identity |
| The model invents order data | Empty tool result and permissive instructions | Tighten instructions; return a clear not-found; never fabricate |
| The agent loops on a failing tool | No tool-call budget configured | Set the budget; confirm the loop stops |

## 14. Teardown and reset

1. Stop services and remove containers; keep the named volume if the data is still needed.
2. Remove the volume only for a full reset — the seed script rebuilds the baseline.
3. Rotate local secret files after any suspected exposure, even locally.
4. Re-run `bootstrap-local.ps1`, then `verify-local.ps1`. A reset is complete only when every check
   passes again.

> **Reset rule:** never repair a failing environment by weakening a control. Removing RLS, granting a
> bypass, or disabling token checks to make a demo work invalidates every test result produced
> afterwards.
