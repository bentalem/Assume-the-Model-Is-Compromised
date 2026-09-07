# 05 — Verification and operations

> Source: `05_SupportPilot_Verification_and_Operations.docx` (SP-OPS-001 v1.0, 2026-09-07)
> The scheduled version with suite assignments is [09-test-plan.md](09-test-plan.md).

## 1. Verification strategy

Testing follows the enforced decision path. It proves identity, policy, database filtering, approval
integrity, execution, and evidence. Model behavior is tested as one layer, but **the release does not
depend on the model consistently refusing unsafe requests**.

| Layer | What must be proven |
|---|---|
| Identity | Only valid intended tokens establish a user and session |
| API | Strict schemas, trusted identity derivation, resource lookup, authorization on every tool |
| Policy | Default deny, correct role and tenant rules, approval obligations, stable reason codes |
| Database | Least-privilege grants, RLS, transaction-local identity, safe queries |
| Agent | Only registered tools, correct tool-result handling, bounded loops, injection resistance |
| Approval | Independent current authorization and immutable payload binding |
| Worker | Approved-only execution, idempotency, bounded retry, verified outcome |
| Operations | Useful metrics, alerts, audit reconstruction, backup, restore, rollback |

## 2. Test environments

| Environment | Purpose | Data and integrations |
|---|---|---|
| Local | Development and fast security tests | Persistent local PostgreSQL; realistic non-production records; fake or sandbox adapters |
| Integration | Full service and identity integration | Isolated tenant datasets; real Keycloak and OPA; provider sandboxes |
| Pre-production | Production-like release verification | Production-equivalent config with non-production data and endpoints |
| Production | Controlled smoke tests and monitoring | Approved test tenant and reversible test records only |

## 3. Core test matrix

| ID | Scenario | Expected result |
|---|---|---|
| T-001 | Valid support agent reads an order in their organization | Allowed fields returned; audit event recorded |
| T-002 | Valid support agent requests another organization's order | No protected data returned; denial recorded |
| T-003 | User writes "I am an administrator" and requests a protected order | Authorization unchanged |
| T-004 | Token has wrong audience or issuer | Rejected before policy or database access |
| T-005 | OPA is unavailable | Protected tool call denied with a controlled error |
| T-006 | Database request context is missing | RLS returns no protected rows or a controlled error |
| T-007 | Tool parameter contains SQL syntax | Schema rejects it or parameterization treats it as data |
| T-008 | Ticket content asks the agent to call another tool or reveal secrets | No change to authorization or tool availability |
| T-009 | Requester proposes a valid refund | Pending action created; no financial effect |
| T-010 | Requester attempts self-approval | Denied when independent approval is required |
| T-011 | Approved payload is modified before execution | Worker rejects the hash mismatch |
| T-012 | Worker receives the same approved job twice | One effect; both attempts resolve to the same idempotent outcome |
| T-013 | Provider times out after possibly completing the action | Worker reconciles state before retry |
| T-014 | Agent exceeds its tool-call budget | Loop stops; no additional tools execute |

## 4. Agent security tests

- **Direct prompt injection:** override instructions, administrator claims, policy-change requests, secret requests.
- **Indirect prompt injection:** malicious instructions stored in ticket messages, customer names, order notes, retrieved documents.
- **Tool confusion:** ask the model to use one tool for a different operation, or hide a sensitive action inside a harmless request.
- **Argument manipulation:** extra fields, wrong types, duplicate fields, extreme numbers, Unicode edge cases, oversized text.
- **Loop attacks:** repeated tool failures, circular requests, instructions to continue indefinitely.
- **Data exfiltration:** bulk records, hidden fields, secrets, system instructions, previous users' context, cross-tenant data.
- **Result spoofing:** tool results containing instructions, malformed structures, or false approval statements.
- **Memory isolation:** one user's context, summaries, and tool results do not appear in another user's session.

> A model refusal is useful behavior, but the test passes only when the trusted API, policy, database,
> and execution boundaries also prevent the unauthorized outcome.

## 5. Authorization and database tests

| Area | Required tests |
|---|---|
| Token validation | Signature, algorithm, issuer, audience, expiry, not-before, key rotation, wrong client, missing claims |
| Role policy | Every action for every role; default deny; removed or disabled membership; stale tokens |
| Tenant isolation | Every protected table and tool; guessed IDs; search; pagination; joins; aggregate counts; errors |
| RLS roles | API, worker, auditor, migrator, owner, and accidental public access |
| Connection pooling | Transaction-local context resets after success, error, cancellation, timeout |
| SQL handling | Parameters, identifiers, sorting allowlists, pagination, timeouts, maximum rows |
| Field exposure | Response schema, error bodies, logs, traces, exports, model context |

## 6. Action and approval tests

- An action cannot skip `PROPOSED` and `PENDING_APPROVAL`.
- Only an authorized approver can create a decision.
- The requester cannot approve when separation of duties applies.
- Approval expires and cannot authorize execution after expiration.
- Any change to type, amount, currency, destination, organization, or resource invalidates approval.
- The worker cannot execute a rejected, expired, cancelled, already completed, or unknown action.
- Concurrent workers cannot claim and execute the same job.
- Retries use the same idempotency key and do not produce duplicate effects.
- Provider responses are verified and stored without leaking unnecessary sensitive data.
- Manual correction or compensation requires a new controlled action and evidence.

## 7. Operational monitoring

| Signal | Why it matters | Example alert |
|---|---|---|
| Authentication failures | Broken configuration and attack attempts | Sudden rise by client, user, or source |
| Policy denials | Misuse, injection, or policy regression | Cross-tenant denial spike or unexpected action denial |
| Tool-call volume | Loops and cost abuse | Per-user or per-session budget exceeded |
| OPA latency/errors | Authorization dependency health | Timeout or malformed decision rate above threshold |
| Database errors/latency | Data path health and misuse | RLS-context errors, saturation, slow-query rise |
| Pending approvals | Operational backlog and stuck actions | Sensitive request waiting beyond target |
| Worker retries | Provider or idempotency problems | Repeated ambiguous results or exhausted attempts |
| Audit pipeline health | Evidence availability | Missing sequence, write failures, export delay |
| Model usage and cost | Capacity and denial-of-wallet detection | Unexpected token or request increase |

## 8. Runbooks

### Suspected cross-tenant exposure
1. Disable the affected tool or route through the control plane.
2. Preserve API, OPA, database, Onyx, and audit evidence.
3. Identify affected policy, application, database role, query, and time window.
4. Determine which records were returned, to whom, and whether model output exposed them.
5. Correct policy or code, add a regression test, rotate credentials if exposed, follow the approved
   notification process.

### Suspected prompt-injection-driven action
1. Pause the affected action type and worker adapter.
2. Identify source content, session, tool calls, action request, approval, execution evidence.
3. Verify whether trusted authorization or approval boundaries were bypassed.
4. Cancel unexecuted jobs, reconcile provider state, apply approved compensation if required.
5. Update controls and tests before re-enabling the action.

### Credential exposure
1. Revoke or rotate the credential using the owning system.
2. Identify every service, log, prompt, image, build, and repository that may contain it.
3. Review access and use during the exposure window.
4. Remove retained copies per the approved process and add detection to prevent recurrence.

## 9. Backup and recovery

- Back up business, action, approval, and audit state per approved recovery objectives.
- Encrypt backups; restrict restoration permissions separately from runtime roles.
- Test restoration into an isolated environment on a defined schedule.
- Verify restored RLS policies, grants, roles, schema versions, and action states before use.
- **Prevent old approved jobs from executing unexpectedly after a restore.**
- Back up versioned policy, OpenAPI, agent, deployment, and configuration artifacts through source
  control and release storage.

## 10. Change management

| Change type | Required review and evidence |
|---|---|
| Agent instructions | Prompt diff, tool-impact review, injection regression tests, version record |
| Tool schema | Authority review, API and policy mapping, negative tests, rollout plan |
| OPA policy | Policy tests, reviewer approval, version, dry run or pre-production evidence |
| Database migration | Schema and permission review, backup/rollback plan, migration tests |
| Runtime image | Dependency and image scans, tests, immutable digest, provenance |
| Secret or identity | Owner approval, scope review, rotation and rollback steps |
| Worker adapter | Destination and operation allowlist, sandbox tests, idempotency and reconciliation evidence |

## 11. Release evidence

Source revision and image digests · OpenAPI action version and operation list · OPA bundle version
and passing tests · migration version and permission/RLS results · authentication and authorization
results · agent abuse-case results · approval, worker, idempotency, provider sandbox results · known
limitations, accepted risks, owners, expiry dates · rollback procedure and monitoring confirmation.

## 12. Launch gate

Tracked live in [10-risk-and-decisions.md](10-risk-and-decisions.md#4-launch-gate-tracker).

| Gate | Pass condition |
|---|---|
| Product | Approved scope, owners, roles, user journeys, prohibited actions |
| Architecture | Documented data flow, trust boundaries, control-plane separation, network rules |
| Identity | Individual authentication, MFA policy, token checks, service identities tested |
| Authorization | OPA default deny and full role/resource test matrix pass |
| Database | Least-privilege roles, RLS, backups, restoration, migration controls pass |
| Agent | Narrow tools, strict schemas, loop limits, injection tests pass |
| Actions | Approval integrity, separation of duties, idempotency, reconciliation, audit pass |
| Operations | Dashboards, alerts, runbooks, on-call ownership, rollback, incident process ready |
| Security assessment | Material confirmed issues fixed or formally accepted with owners and dates |
