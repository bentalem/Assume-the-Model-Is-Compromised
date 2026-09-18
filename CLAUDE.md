# SupportPilot — the invariants

SupportPilot is a lab for learning how to secure AI agents. The model proposes tool use; trusted
services decide what is allowed and perform every real action.

This file is the contract for changing the code. It is also, read on its own, the shortest statement
of what the lab is teaching — every rule below is enforced somewhere you can go and look at.

Read [`docs/architecture/`](docs/architecture/) before starting work.

## Non-negotiable rules

Breaking one invalidates every test result produced after it. If a change appears to require breaking
one, that is the finding — stop and write it down rather than working around it.

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
6. **Request context is transaction-local.** Always `BEGIN` plus `SET LOCAL app.user_id` and
   `app.organization_id` in the same transaction as the query. Never `SET` on a pooled connection.
7. **The model never gets a generic tool.** No SQL, shell, file, or unrestricted HTTP tool. Only the
   registered business operations in [`specs/api-contract.md`](specs/api-contract.md).
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
- **Every capability ships with tests**: one positive, one negative, one cross-tenant. A change is not
  done without them.
- **Fixed test data.** Use the baseline in
  [`docs/08-local-build-runbook.md`](docs/08-local-build-runbook.md#2-test-data-baseline):
  `cedar` / `northwind`, alice / bob / fiona / dana / mallory, `ORD-2001` / `ORD-3001`, `TKT-1001`.
  Do not invent organizations or users inside a test.
- **Control-plane changes are not ordinary code changes.** A new tool, a new grant, a new policy rule,
  or a new outbound destination is a privilege grant. Say so in the change, and update
  [`docs/architecture/`](docs/architecture/) in the same commit.
- **A test is named for what it proves.** If the name is a larger claim than the assertion, change one
  of them. "Bulk extraction is impossible" once meant "a single page was capped" — and bulk extraction
  turned out to be entirely possible by paging.
- **When something does not happen, establish whether it was prevented or whether it merely failed.**
  A malformed request that never reached the authorization pipeline is not proof that authorization
  worked.
- **Never assert that the model refused.** Two identical runs produce different tool calls, so any
  assertion about model behaviour is unstable and proves nothing. Test the boundary around it.

## Never fix a failing environment by weakening a control

None of these may be accepted, not even temporarily, not even "just in the test tenant":

- disable row-level security, or grant `BYPASSRLS`
- let the API own protected tables
- add a cached or fallback allow path for when OPA is unavailable
- accept an organization or user id from a tool argument
- register a generic SQL, shell, or HTTP tool
- let the API execute a refund directly
- let a requester approve their own action
- mount the migration credential into a runtime service
- skip an audit write for latency

If a demo only works with one of these, the demo is the thing that is wrong.

## Definition of done

- Written purpose, and the enforcement point named.
- Tool schema exposes only required parameters and response fields.
- Positive, negative, cross-tenant, and malformed-input tests pass.
- Policy, grants, and RLS behavior tested where applicable.
- Sensitive actions have approval, payload integrity, idempotency, and audit evidence.
- No secret in source, images, prompts, or logs.
- `./scripts/verify-local.ps1` passes every check.
- Docs updated.
