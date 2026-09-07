# 07 — Task backlog

> Source: `07_SupportPilot_Work_Breakdown_and_Backlog.docx` (SP-PLAN-002 v1.0, 2026-09-07)
> **This is the working tracker.** Check a box only when the closing evidence exists.

**Progress:** 26 / 99 tasks · current phase: **1** · next task: `P1-03` (MFA policy)

Phase 0 is complete except its gate review (`P0-12`). Phase 1 is complete except the three
tasks that need Onyx running (`P1-04`, `P1-16`) or a decision (`P1-03`), plus `P1-19`/`P1-20`.
Evidence: `evidence/verify-local-*.json` — 16/16 environment checks, 70 API tests, 14 policy tests.

Size: `S` ≤ 1 day · `M` 2–3 days · `L` ≥ 4 days (split if it cannot finish in a week).

**Backlog rule:** no task may add a tool, database grant, policy rule, or outbound destination that is
not already in the baseline. That is a control-plane change and follows
[05-verification-and-operations.md](05-verification-and-operations.md#10-change-management) first.

---

## Phase 0 — Project baseline (W01–W02, → M0)

*Goal: a clean machine reaches a verified running environment with one command, with the final
network and secret boundaries already in place.*

- [x] **P0-01** `WS-A` `S` — Create the repository structure from [04](04-build-and-deployment.md#2-repository-structure) with README and code owners.
      *Evidence:* tree matches the baseline layout. *Deps:* —
- [x] **P0-02** `WS-A` `S` — Record coding standards, review rules, branch protection for policy, schema, tool changes.
      *Evidence:* protected branches configured and documented. *Deps:* P0-01
- [x] **P0-03** `WS-H` `S` — Copy the threat model into `docs/architecture/` and open `docs/decisions/`.
      *Evidence:* threat model and first decision records committed. *Deps:* P0-01
- [x] **P0-04** `WS-A` `M` — Pin container image digests and dependency versions for every service.
      *Evidence:* lock files and pinned digests; no floating tags. *Deps:* P0-01
- [x] **P0-05** `WS-A` `M` — Create separate Docker networks for edge, app, policy, data traffic.
      *Evidence:* PostgreSQL and OPA unreachable from the edge network (check `V-02`). *Deps:* P0-04
- [x] **P0-06** `WS-A` `L` — Define compose services: Onyx, Keycloak, API, OPA, PostgreSQL, worker, approval portal, migration job.
      *Evidence:* all services start; the migration job runs once and exits. *Deps:* P0-05
- [x] **P0-07** `WS-A` `M` — Create local secret files with per-service mounts; exclude from version control.
      *Evidence:* no secret in the repo; each service mounts only its own. *Deps:* P0-06
- [x] **P0-08** `WS-A` `S` — Write `.env.example` with names and safe defaults only.
      *Evidence:* no real credential in the file. *Deps:* P0-07
- [x] **P0-09** `WS-A` `M` — Add health checks and readiness dependencies to every service.
      *Evidence:* environment reports healthy without manual retries. *Deps:* P0-06
- [x] **P0-10** `WS-A` `M` — Write `scripts/bootstrap-local.ps1` and `scripts/verify-local.ps1`.
      *Evidence:* one command starts; one command reports pass/fail per check. *Deps:* P0-09
- [x] **P0-11** `WS-I` `S` — Add secret-scanning and formatting to pre-commit or pipeline.
      *Evidence:* a committed test secret is blocked. *Deps:* P0-02
- [ ] **P0-12** `WS-A` `S` — Run the phase 0 gate review.
      *Evidence:* signed gate record for M0. *Deps:* P0-10, P0-11

## Phase 1 — Identity and one protected read (W03–W05, → M1)

*Goal: an authenticated user reads one authorized order end to end; the same request for another
organization is denied at both the API and the database.*

- [x] **P1-01** `WS-B` `M` — Create the Keycloak realm, clients, redirect addresses, groups, roles.
      *Evidence:* realm export committed; login works. *Deps:* P0-12
- [x] **P1-02** `WS-B` `S` — Create test users and memberships (alice, bob, fiona, dana, mallory).
      *Evidence:* each user signs in with the expected roles. *Deps:* P1-01
- [ ] **P1-03** `WS-B` `S` — Enable the required MFA policy for the local realm.
      *Evidence:* login requires the configured second factor. *Deps:* P1-01
- [ ] **P1-04** `WS-F` `L` — Configure Onyx authentication and individual OAuth forwarding for the action.
      *Evidence:* the API receives a user-bound token, not a service token. *Deps:* P1-01
- [x] **P1-05** `WS-B` `L` — Build token verification middleware (issuer, audience, signature, algorithm, expiry, nbf, key cache).
      *Evidence:* every negative token test rejects before policy or database access. *Deps:* P1-01
- [x] **P1-06** `WS-D` `M` — Migration: organizations, users, memberships, customers, orders.
      *Evidence:* applies cleanly on an empty database. *Deps:* P0-12
- [x] **P1-07** `WS-D` `M` — Create `sp_migrator_role`, `sp_api_role`, `sp_worker_role`, `sp_auditor_role` with least-privilege grants.
      *Evidence:* runtime roles have no ownership, no `BYPASSRLS`, no schema privileges. *Deps:* P1-06
- [x] **P1-08** `WS-D` `M` — Enable and force RLS on phase 1 tables; add tenant policies.
      *Evidence:* zero rows when request context is missing (check `V-04`). *Deps:* P1-07
- [x] **P1-09** `WS-D` `M` — Implement transaction-local request context (`SET LOCAL`).
      *Evidence:* pooled-connection test shows no context leak (check `V-12`). *Deps:* P1-08
- [x] **P1-10** `WS-D` `S` — Seed two organizations, users, customers, orders incl. `ORD-2001`, `ORD-3001`.
      *Evidence:* repeatable seed producing known test data. *Deps:* P1-08
- [x] **P1-11** `WS-E` `M` — Build the trusted resource lookup loading order attributes before policy evaluation.
      *Evidence:* policy input contains server-side attributes only. *Deps:* P1-09
- [x] **P1-12** `WS-C` `M` — Implement the OPA client with a short timeout; deny on unavailable, undefined, malformed.
      *Evidence:* stopping OPA denies with a controlled error (check `V-09`). *Deps:* P1-05
- [x] **P1-13** `WS-C` `M` — Write the first OPA rule for `order.read` with default deny, reason code, policy version.
      *Evidence:* policy unit tests pass for allow and deny. *Deps:* P1-12
- [x] **P1-14** `WS-E` `M` — Build `get_order` with a strict path pattern and bounded response schema.
      *Evidence:* malformed identifiers rejected by schema before lookup. *Deps:* P1-11, P1-13
- [x] **P1-15** `WS-F` `S` — Publish the OpenAPI 3.1 document containing only `get_order`.
      *Evidence:* document validates; exactly one operation. *Deps:* P1-14
- [ ] **P1-16** `WS-F` `M` — Register the action in Onyx; set agent instructions for tool use and error handling.
      *Evidence:* the model can call `get_order` and nothing else. *Deps:* P1-15, P1-04
- [x] **P1-17** `WS-E` `S` — Add correlation identifiers across Onyx, API, OPA, database.
      *Evidence:* one request reconstructable from logs across services. *Deps:* P1-14
- [x] **P1-18** `WS-E` `M` — Write audit events for an allowed and a denied order read.
      *Evidence:* rows contain actor, action, resource, decision, policy version, request id. *Deps:* P1-14
- [ ] **P1-19** `WS-H` `M` — Run `T-001`…`T-007`; store results.
      *Evidence:* all seven pass with stored evidence. *Deps:* P1-16, P1-18
- [ ] **P1-20** `WS-B` `S` — Run the phase 1 gate review.
      *Evidence:* signed gate record for M1. *Deps:* P1-19

## Phase 2 — Complete read capabilities (W06–W08, → M2)

*Goal: the full read surface with minimized responses, pagination, audit coverage, and proven
resistance to instructions stored in business data.*

- [ ] **P2-01** `WS-D` `M` — Extend schema: order items, shipments, tickets, ticket messages, internal notes. *Deps:* P1-20
- [ ] **P2-02** `WS-D` `M` — Add RLS policies and role grants for every new table. *Deps:* P2-01
- [ ] **P2-03** `WS-E` `L` — Build `search_customers` with mandatory pagination and maximum result size. *Deps:* P2-02
- [ ] **P2-04** `WS-E` `M` — Build `get_customer` with an approved field subset. *Deps:* P2-02
- [ ] **P2-05** `WS-E` `L` — Build `get_ticket` with permitted conversation history and visibility rules. *Deps:* P2-02
- [ ] **P2-06** `WS-E` `M` — Extend `get_order` with items and shipment status under the same authorization path. *Deps:* P2-02
- [ ] **P2-07** `WS-C` `L` — Add OPA rules and tests for `customer.read`, `ticket.read`, and field obligations. *Deps:* P2-03
- [ ] **P2-08** `WS-E` `M` — Apply obligations so denied fields are removed before the response is built. *Deps:* P2-07
- [ ] **P2-09** `WS-D` `M` — Add sorting allowlists, query timeouts, maximum row limits to all read repositories. *Deps:* P2-03
- [ ] **P2-10** `WS-E` `M` — Audit events for every allowed and denied tool call with stable reason codes. *Deps:* P2-06
- [ ] **P2-11** `WS-F` `M` — Extend the OpenAPI document; no open objects or unbounded arrays. *Deps:* P2-06
- [ ] **P2-12** `WS-F` `M` — Configure model-call, tool-call, time, token, and cost budgets. *Deps:* P2-11
- [ ] **P2-13** `WS-H` `M` — Seed prompt-injection records into ticket messages, customer names, order notes. *Deps:* P2-05
- [ ] **P2-14** `WS-H` `L` — Build the agent abuse suite (`TS-7`): direct, indirect, tool confusion, argument manipulation. *Deps:* P2-13
- [ ] **P2-15** `WS-H` `M` — Add exfiltration and memory-isolation tests across two users and two organizations. *Deps:* P2-14
- [ ] **P2-16** `WS-H` `M` — Add response and log redaction checks for secrets and excessive fields. *Deps:* P2-10
- [ ] **P2-17** `WS-H` `M` — Run `T-008`, `T-014`, and the abuse suite; store results. *Deps:* P2-14, P2-12
- [ ] **P2-18** `WS-E` `S` — Run the phase 2 gate review. *Evidence:* signed gate record for M2. *Deps:* P2-17

## Phase 3 — Controlled low-impact writes (W09–W10, → M3)

*Goal: one controlled write, with authorship from verified identity and proven concurrency and audit
behavior.*

- [ ] **P3-01** `WS-D` `M` — Add internal note constraints: length, content type, ticket ownership, organization. *Deps:* P2-18
- [ ] **P3-02** `WS-D` `M` — Add insert policies for internal notes, API role only. *Deps:* P3-01
- [ ] **P3-03** `WS-E` `M` — Build `add_internal_note` with strict schema and **server-derived** author identity. *Deps:* P3-02
- [ ] **P3-04** `WS-C` `M` — Add OPA rules and tests for `note.create`, incl. role and ticket-state conditions. *Deps:* P3-03
- [ ] **P3-05** `WS-E` `M` — Add expected-current-state checks to prevent stale writes. *Deps:* P3-03
- [ ] **P3-06** `WS-E` `M` — Write business state and audit evidence in one transaction. *Evidence:* a forced audit failure rolls back the note. *Deps:* P3-05
- [ ] **P3-07** `WS-H` `M` — Negative tests: cross-tenant ticket, unauthorized role, oversized content, injected instructions in note text. *Deps:* P3-06
- [ ] **P3-08** `WS-F` `S` — Register the write operation in the OpenAPI document and Onyx agent. *Deps:* P3-06
- [ ] **P3-09** `WS-H` `S` — Run the phase 3 test set; store results. *Deps:* P3-07, P3-08
- [ ] **P3-10** `WS-E` `S` — Run the phase 3 gate review. *Evidence:* signed gate record for M3. *Deps:* P3-09

## Phase 4 — Approval and worker (W11–W14, → M4)

*Goal: a refund can be proposed, independently approved, and executed exactly once, with evidence at
every transition.*

- [ ] **P4-01** `WS-D` `L` — Create `action_requests`, `approval_decisions`, `action_jobs`, `action_executions`, idempotency tables. *Deps:* P3-10
- [ ] **P4-02** `WS-D` `M` — RLS and grants so the worker role cannot read broad customer data. *Deps:* P4-01
- [ ] **P4-03** `WS-G` `L` — Implement the action state machine with allowed transitions and guards. *Deps:* P4-01
- [ ] **P4-04** `WS-G` `M` — Compute and store an immutable payload hash at proposal time. *Deps:* P4-03
- [ ] **P4-05** `WS-E` `L` — Build `propose_refund` with order, amount, currency, reason validation and business limits. *Deps:* P4-04
- [ ] **P4-06** `WS-E` `M` — Build `get_action_status` returning only permitted state fields. *Deps:* P4-03
- [ ] **P4-07** `WS-C` `L` — OPA rules for `refund.propose` and `refund.approve`, incl. limits and separation of duty. *Deps:* P4-05
- [ ] **P4-08** `WS-G` `L` — Approval portal view showing the exact immutable payload and risk details. *Deps:* P4-05
- [ ] **P4-09** `WS-G` `M` — Re-check approver authorization at decision time with a current token. *Deps:* P4-08
- [ ] **P4-10** `WS-G` `M` — Record approval, rejection, comment, policy version, timestamp, expiry. *Deps:* P4-09
- [ ] **P4-11** `WS-G` `M` — Action coordinator queues only valid unexpired approvals. *Deps:* P4-10
- [ ] **P4-12** `WS-G` `L` — Worker job claim with an atomic lease; no double claim. *Deps:* P4-11
- [ ] **P4-13** `WS-G` `M` — Verify approval state, expiry, payload hash, idempotency reservation before execution. *Deps:* P4-12
- [ ] **P4-14** `WS-G` `L` — Refund provider adapter with destination, method, operation allowlists. *Deps:* P4-13
- [ ] **P4-15** `WS-G` `M` — Bounded retries with provider state checks for ambiguous timeouts. *Deps:* P4-14
- [ ] **P4-16** `WS-G` `M` — Store outcome evidence; complete or release the job transactionally. *Evidence:* no job stuck in `EXECUTING` after a crash test. *Deps:* P4-15
- [ ] **P4-17** `WS-G` `M` — Audit events for propose, approve, reject, queue, execute, succeed, fail. *Deps:* P4-16
- [ ] **P4-18** `WS-F` `M` — Register `propose_refund` and `get_action_status`. *Evidence:* the model can propose but not approve or execute. *Deps:* P4-06
- [ ] **P4-19** `WS-G` `M` — Build the fake provider; connect the sandbox provider where available. *Evidence:* both pass the same contract tests. *Deps:* P4-14
- [ ] **P4-20** `WS-H` `L` — Run `T-009`…`T-013` plus concurrency and crash-recovery tests. *Deps:* P4-17, P4-19
- [ ] **P4-21** `WS-I` `M` — Write the reconciliation procedure for ambiguous or failed executions. *Deps:* P4-16
- [ ] **P4-22** `WS-G` `S` — Run the phase 4 gate review. *Evidence:* signed gate record for M4. *Deps:* P4-20, P4-21

## Phase 5 — Hardening and operational readiness (W15–W18, → M5/M6)

*Goal: the system can be operated, observed, recovered, and released under change control.*

- [ ] **P5-01** `WS-I` `L` — Select the production secret manager; move every secret out of file mounts. *Deps:* P4-22
- [ ] **P5-02** `WS-I` `M` — Adopt workload identity for API and worker where supported. *Deps:* P5-01
- [ ] **P5-03** `WS-I` `M` — Centralized logs with redaction rules and retention. *Deps:* P4-22
- [ ] **P5-04** `WS-I` `L` — Metrics and traces across Onyx, API, OPA, database, worker. *Deps:* P5-03
- [ ] **P5-05** `WS-I` `M` — Create the alerts from [05 §7](05-verification-and-operations.md#7-operational-monitoring) with thresholds and owners. *Deps:* P5-04
- [ ] **P5-06** `WS-I` `M` — Dashboards for authentication failures, denials, tool volume, worker retries, cost. *Deps:* P5-04
- [ ] **P5-07** `WS-I` `M` — Encrypted backups for business, action, approval, audit state. *Deps:* P4-22
- [ ] **P5-08** `WS-I` `L` — Restore into an isolated environment; verify roles, grants, RLS, action states. *Deps:* P5-07
- [ ] **P5-09** `WS-I` `M` — Write the three incident runbooks. *Evidence:* rehearsed at least once. *Deps:* P4-22
- [ ] **P5-10** `WS-I` `M` — Add dependency, secret, source, image, infrastructure scans to the pipeline. *Deps:* P4-22
- [ ] **P5-11** `WS-I` `M` — Immutable versioned images with provenance and dependency inventory. *Deps:* P5-10
- [ ] **P5-12** `WS-H` `L` — Stand up the isolated test environment; run full authorization and action suites. *Deps:* P5-11
- [ ] **P5-13** `WS-H` `L` — Run application, API, agent, authorization, infrastructure security assessments. *Deps:* P5-12
- [ ] **P5-14** `WS-I` `L` — Load, failure, recovery, rollback tests incl. OPA and database outage behavior. *Deps:* P5-12
- [ ] **P5-15** `WS-I` `M` — Complete change-management records for prompts, tools, policy, schema, images, secrets, adapters. *Deps:* P5-13
- [ ] **P5-16** `WS-I` `M` — Assemble the release evidence package. *Deps:* P5-14, P5-15
- [ ] **P5-17** `WS-I` `S` — Run the launch gate review. *Evidence:* signed launch decision for M6. *Deps:* P5-16

## Standing tasks (never close)

| ID | Task | WS | Cadence |
|---|---|---|---|
| ST-01 | Update the threat model when a tool, destination, role, or data flow changes | WS-H | Per change |
| ST-02 | Review every new or changed tool schema for minimum parameters and fields | WS-H | Weekly |
| ST-03 | Run the abuse and injection suite against the current tool surface | WS-H | Per phase and tool change |
| ST-04 | Confirm runtime roles still hold no ownership and no bypass privilege | WS-D | Per migration |
| ST-05 | Confirm no secret in source, images, prompts, logs, or model context | WS-I | Weekly |
| ST-06 | Review OPA default-deny behavior and reason-code stability | WS-C | Per policy change |
| ST-07 | Update decision records for accepted decisions | WS-H | Per decision |
| ST-08 | Review open decisions and risks | WS-I | Monthly |

## Definition of ready

- States one business or security outcome, not an implementation preference.
- Dependencies closed or explicitly waived by the workstream owner.
- Authorization effect understood: which subject, action, resource, and policy rule.
- Test cases exist, incl. one negative and one cross-tenant where data is touched.
- Requires no new authority for the model, a runtime service, or a database role.
- Any required open decision is answered.
