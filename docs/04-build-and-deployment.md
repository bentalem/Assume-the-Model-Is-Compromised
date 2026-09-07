# 04 — Build and deployment

> Source: `04_SupportPilot_Build_and_Deployment_Plan.docx` (SP-BUILD-001 v1.0, 2026-09-07)
> The scheduled, task-level version is [06-action-plan.md](06-action-plan.md) and
> [07-task-backlog.md](07-task-backlog.md).

## 1. Build strategy

Build the final security boundaries from the beginning. Each phase produces a working vertical slice
and adds capability **without replacing** the identity, authorization, database, approval, or audit
model.

**Build rule:** a phase is complete only when its positive **and negative** authorization tests pass.
A successful chat response alone is not completion.

## 2. Repository structure

```
supportpilot/
  README.md
  compose.yaml
  .env.example
  docs/ { architecture/ decisions/ runbooks/ }
  services/
    api/       src/ { auth/ policy/ tools/ repositories/ audit/ } tests/ Dockerfile
    worker/    src/ { jobs/ adapters/ idempotency/ }             tests/ Dockerfile
    approval-portal/ src/ tests/ Dockerfile
  database/  { migrations/ seeds/ tests/ }
  policy/    { supportpilot/ tests/ }
  openapi/   supportpilot-actions.yaml
  infrastructure/ { local/ production/ }
  scripts/   { bootstrap-local.ps1 verify-local.ps1 }
```

## 3. Local services

| Service | Container | Persistent data | Exposed access |
|---|---|---|---|
| Onyx | `onyx-*` | Onyx volumes | Users via reverse proxy |
| Keycloak | `supportpilot-keycloak` | Identity database or schema | Login via proxy; admin restricted |
| API | `supportpilot-api` | None (state in PostgreSQL) | Internal action endpoint; local health endpoint |
| OPA | `supportpilot-opa` | Read-only versioned bundle | Private service network only |
| PostgreSQL | `supportpilot-postgres` | Named volume | Private database network only |
| Approval portal | `supportpilot-approval` | None | Approvers via reverse proxy |
| Worker | `supportpilot-worker` | None | No public inbound |
| Migration job | `supportpilot-migrate` | Writes schema state | One-shot deployment job |

## 4. Build phases

### Phase 0 — Project baseline
Repository structure, coding standards, threat model, decision records · pinned images and
dependencies · separate networks for edge, application, policy, database · local secret files
excluded from version control · health checks and one command to start or verify.

### Phase 1 — Identity and one protected read
Keycloak realm, clients, redirects, users, groups, roles · Onyx authentication and individual OAuth
forwarding · API token-verification middleware · `get_order` endpoint and strict OpenAPI schema ·
first OPA rule and tests · organizations, users, memberships, customers, orders with RLS · confirm
same-tenant access and cross-tenant denial end to end.

### Phase 2 — Complete read capabilities
Customer search, customer details, ticket details, order items, shipment status · field-level
response schemas and pagination · audit events for allowed and denied tool calls · prompt-injection
records in tickets, confirmed unable to change authorization · model and tool-call budgets.

### Phase 3 — Controlled low-impact writes
Internal-note creation with ownership, length, and content constraints · database checks and policies
for organization and ticket visibility · author from verified identity, not model arguments ·
concurrency protection and audit evidence.

### Phase 4 — Approval and worker
Action request, decision, job, execution, idempotency tables · `propose_refund` and
`get_action_status` · approval portal with independent approver authorization · worker, job lease,
retry policy, immutable payload checks, provider adapter · confirm no protected effect before
approval and no effect twice.

### Phase 5 — Hardening and operational readiness
Production secret manager and workload identity · centralized logs, metrics, traces, alerts, backups,
restoration tests, incident runbooks · dependency, image, infrastructure, and policy checks in the
pipeline · application, API, agent, authorization, and infrastructure security assessments · load,
failure, recovery, and rollback testing.

## 5. Configuration

The example environment file contains names and safe defaults only. Real secret values are never
committed.

| Setting | Owner | Purpose |
|---|---|---|
| `KEYCLOAK_ISSUER` | API config | Expected token issuer |
| `SUPPORTPILOT_AUDIENCE` | API config | Required token audience |
| `OPA_URL` | API config | Private OPA decision endpoint |
| `DATABASE_HOST` / `DATABASE_NAME` | API and worker config | Database location without credentials |
| `API_DATABASE_SECRET_FILE` | API secret mount | Restricted API database credential |
| `WORKER_DATABASE_SECRET_FILE` | Worker secret mount | Restricted worker database credential |
| `ACTION_MAX_AMOUNT` | Versioned policy/data | Hard upper bound for an action type |
| `AGENT_MAX_TOOL_CALLS` | Agent runtime | Maximum tool calls in one user turn |
| `AUDIT_RETENTION_DAYS` | Operations config | Approved audit retention period |

## 6. Database migration

1. The pipeline builds and tests the migration artifact.
2. A reviewer approves schema, grant, function, and policy changes.
3. The one-shot migration job receives the migration credential.
4. The job checks the current schema version and applies forward migrations transactionally where possible.
5. The job runs database permission and RLS smoke tests.
6. The job records the version and exits. **Runtime services never receive the migration credential.**

## 7. Onyx integration

- Create an OpenAPI 3.1 document containing **only** approved SupportPilot action endpoints.
- Give each operation a narrow operation id, clear description, strict request schema, bounded response schema.
- Configure individual OAuth authentication so SupportPilot receives the user identity.
- Register the action with the agent and confirm the model can call only listed operations.
- Set agent instructions that explain when to use tools and how to treat tool errors **without
  claiming extra authority**.
- Test tool calls with normal text, administrator claims, malformed identifiers, and indirect
  instructions stored in data.

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
          schema:
            type: string
            pattern: "^ORD-[0-9]{4,12}$"
      responses:
        "200": { description: Authorized order result }
        "404": { description: Not found or not allowed }
```

## 8. OPA integration

- Run OPA on a private network with policy loaded from a read-only versioned bundle.
- The API sends structured input and applies a short timeout.
- The API treats unavailable, undefined, or malformed decisions as **deny**.
- Policy unit tests run before a bundle can be published.
- Every decision records the policy version and stable reason code.
- Only the control-plane deployment identity can publish a new policy bundle.

## 9. Worker and approval portal

**Approval portal:** display action type, requester, organization, resource, amount, destination,
reason, risk level, expiration · display the exact immutable payload that will execute · require a
current approver token and re-check authorization at decision time · prevent self-approval where
policy requires independence · record approval, rejection, comment, policy version, timestamp.

**Worker:** claim one queued job atomically with a lease · verify approval state, expiry, payload
hash, and idempotency before execution · use a dedicated adapter per provider · allow only configured
destinations, methods, and operation types · bounded retries with provider-state checks for ambiguous
timeouts · store outcome evidence and release or complete the job transactionally.

## 10. Deployment pipeline

1. Formatting, static analysis, unit tests, policy tests, migration tests.
2. Scan dependencies, secrets, source, container images, infrastructure configuration.
3. Build immutable versioned images; generate provenance and dependency inventory.
4. Deploy to an isolated test environment.
5. Run authentication, authorization, RLS, tool, approval, idempotency, and failure tests.
6. Require review for production policy, schema, tool, and infrastructure changes.
7. Deploy with a documented rollback path; monitor health and security signals.

## 11. Production readiness

| Area | Required before production |
|---|---|
| Identity | Production realm, MFA policy, account lifecycle, service identities, key rotation |
| Data | Approved classification, retention, encryption, backups, restoration test, migration plan |
| Network | Private service networks, TLS, egress allowlists, restricted administration |
| Application | Security review, error handling, rate limits, concurrency and load tests |
| Agent | Prompt-injection tests, tool-call limits, output minimization, safe failure behavior |
| Actions | Approval policy, provider sandbox tests, idempotency, reconciliation, rollback/compensation |
| Operations | Metrics, alerts, logs, traces, on-call ownership, incident and recovery runbooks |
| Governance | Named owners, reviewed policies, change control, risk acceptance, launch approval |

## 12. Definition of done

See [CLAUDE.md](../CLAUDE.md#definition-of-done) — it is the same list, kept there because every
change must satisfy it.
