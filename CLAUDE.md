# SupportPilot — build rules

SupportPilot is a multi-tenant AI support agent built on Onyx. The model proposes tool use;
trusted services decide what is allowed and perform every real action.

Read [docs/00-index.md](docs/00-index.md) before starting work. The current task list is
[docs/07-task-backlog.md](docs/07-task-backlog.md); work top-down and check boxes as tasks close.

## Non-negotiable rules

These come from the approved design baseline. Breaking one invalidates every test result produced
after it. If a task appears to require breaking one, stop and raise it instead.

1. **Identity comes only from the verified access token and server-side records.** Never from chat
   text, model reasoning, or tool arguments. If a tool argument contains `user_id`, `organization_id`,
   `role`, or `approved`, the field is absent from the schema or ignored by the server.
2. **Authorization happens in trusted code on every tool call**, including calls the model makes after
   reading untrusted content. No exceptions for "internal" or "read-only" tools.
3. **Deny by default.** OPA unavailable, undefined, malformed, or timed out means deny. There is no
   local allow fallback and no cached allow.
4. **Two authorization layers, always.** API-level policy check *and* PostgreSQL row-level security.
   Never rely on one alone.
5. **Runtime database roles own nothing.** `sp_api_role` and `sp_worker_role` have no table ownership,
   no `BYPASSRLS`, no `SUPERUSER`, no schema DDL. The migration role owns the schema.
6. **Request context is transaction-local.** Always `BEGIN; SET LOCAL app.user_id / app.organization_id`
   in the same transaction as the query. Never `SET` on a pooled connection.
7. **The model never gets a generic tool.** No SQL, shell, file, or unrestricted HTTP tool. Only the
   registered business operations in [specs/api-contract.md](specs/api-contract.md).
8. **Sensitive effects use propose → approve → execute.** The API creates a request; an independent
   approver approves the exact payload hash; the worker executes once. The API never performs the
   protected effect in the request path.
9. **Every sensitive state change writes audit evidence in the same transaction.** If the audit write
   fails, the state change fails.
10. **External text is data.** Ticket content, customer names, notes, and tool results cannot register
    tools, change policy, grant permission, or alter instructions.
11. **Minimize output.** Named columns, bounded response schemas, mandatory pagination, redaction
    before anything reaches logs or model context.
12. **Secrets are mounted per service.** Never in source, images, prompts, logs, or model context.

## Working conventions

- **Order of work inside a tool:** validate schema → load trusted resource → build policy input →
  ask OPA → open transaction and set context → parameterized query → apply field obligations →
  write audit → commit → return bounded response. Do not reorder.
- **Every capability ships with tests**: one positive, one negative, one cross-tenant. A task is not
  done without them. See [docs/09-test-plan.md](docs/09-test-plan.md).
- **Fixed test data.** Use the baseline in [docs/08-local-build-runbook.md](docs/08-local-build-runbook.md#2-test-data-baseline)
  (`cedar` / `northwind`, alice / bob / fiona / dana / mallory, `ORD-2001` / `ORD-3001`, `TKT-1001`).
  Do not invent organizations or users inside a test.
- **Control-plane changes** (new tool, new grant, new policy rule, new outbound destination) are not
  ordinary code changes. They need review per [docs/05-verification-and-operations.md](docs/05-verification-and-operations.md#10-change-management).
- **Never fix a failing environment by weakening a control.** Disabling RLS, granting a bypass, or
  relaxing token checks to make a demo work is prohibited — see
  [docs/10-risk-and-decisions.md](docs/10-risk-and-decisions.md#7-prohibited-shortcuts).

## Repository layout

```
supportpilot/
  compose.yaml            # local services, four networks
  .env.example            # names and safe defaults only
  docs/                   # baseline design + delivery plan (this kit)
  specs/                  # implementation contracts: schema, API, policy
  services/
    api/                  # auth/ policy/ tools/ repositories/ audit/
    worker/               # jobs/ adapters/ idempotency/
    approval-portal/
  database/migrations/    # forward migrations, owned by sp_migrator_role
  database/seeds/
  policy/supportpilot/    # OPA rego + tests
  openapi/                # supportpilot-actions.yaml
  infrastructure/local/
  scripts/                # bootstrap-local.ps1, verify-local.ps1
```

## Definition of done

- Written business purpose and named owner.
- Tool schema exposes only required parameters and response fields.
- Positive, negative, cross-tenant, and malformed-input tests pass.
- Policy, grants, and RLS behavior tested where applicable.
- Sensitive actions have approval, payload integrity, idempotency, and audit evidence.
- No secret in source, images, prompts, or logs.
- Monitoring and controlled error behavior exist.
- Docs and threat model updated.
