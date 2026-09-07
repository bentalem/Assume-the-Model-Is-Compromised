# 10 — Risk, decision, and gate register

> Source: `10_SupportPilot_Risk_Decision_and_Gate_Register.docx` (SP-PLAN-005 v1.0, 2026-09-07)
> **Live document.** Updated at every phase gate and reviewed monthly.

**Register rule:** an item is never closed by time passing. It is closed by a decision, by evidence,
or by a recorded acceptance with an owner and an expiry date.

## 1. Fields

| Field | Meaning |
|---|---|
| Status | Open, Decided, Mitigated, Accepted, Closed |
| Owner | The single accountable person. A role name here is itself an open item |
| Needed by | The phase that cannot complete while the item is open |
| Default | What happens with no decision — never a silent weakening of a control |
| Evidence | Gate record, test result, decision record, or runbook |

## 2. Open decisions

| ID | Decision required | Owner | Needed by | Default if not decided | Status |
|---|---|---|---|---|---|
| OD-01 | System of record: keep local PostgreSQL, or integrate the existing support system through adapters | Product owner | Phase 5 | Continue with local PostgreSQL; production migration becomes an open launch condition | Open |
| OD-02 | Financial integration: which provider and sandbox the refund adapter targets | Product owner + Finance | Phase 4 | Phase 4 completes against the fake adapter only; provider evidence becomes a launch-gate condition | Open |
| OD-03 | Tenant model: single database with RLS, or physical separation for some customers | Security lead + Product owner | Phase 5 | Keep the single-database model; regulatory review recorded as outstanding | Open |
| OD-04 | Deployment platform and managed services for production | Operations lead | Phase 5 | Phase 5 targets Docker Compose, which is **not** accepted for production launch | Open |
| OD-05 | Availability targets and SLOs | Product owner + Operations | Phase 5 | No objectives means no meaningful alert thresholds; monitoring stays generic | Open |
| OD-06 | Data retention periods for audit and business records | Legal + Product owner | Phase 5 | Retention stays configurable but unapproved, blocking the governance gate row | Open |
| OD-07 | Refund approval limits per role and the exact separation-of-duty rule | Finance + Security lead | Phase 4 | Most restrictive reading: always an independent approver, lowest configured limit | Open |
| OD-08 | Whether prompts and full model conversations are stored, and under which purpose, access policy, retention, and redaction rules | Security lead + Legal | Phase 2 | Conversations are **not** stored as audit evidence; only structured audit events | Open |
| OD-09 | Named owners for every workstream | Engineering lead | Phase 0 | The plan cannot be baselined; gates lack accountable owners | Open |
| OD-10 | MFA policy and account lifecycle for production identities | Identity engineer + Security lead | Phase 5 | The local MFA policy is carried forward untested against production requirements | Open |

## 3. Risk register

Likelihood/impact: low · medium · high.

| ID | Risk | L | I | Mitigation | Early signal | Owner |
|---|---|---|---|---|---|---|
| R-01 | Onyx→Keycloak individual OAuth forwarding takes longer than planned and blocks the critical path | H | H | Start `P1-04` in W03 in parallel with token verification; keep a documented harness that calls the API directly with a user token | No user-bound token reaching the API by end of W04 | Identity engineer |
| R-02 | RLS added after application queries exist; a table ends up owned by a runtime role | M | H | Create roles and ownership in the first migration; run `TS-3` on every migration | A migration creating a table without an explicit owner | Database engineer |
| R-03 | Field minimization skipped under pressure; responses expose more than approved | M | M | Bounded response schemas in the OpenAPI document; obligations tested in `TS-2` and `TS-5` | A response schema with an open object or unbounded array | Backend engineer |
| R-04 | Agent abuse testing slips to phase 5; injection defects found late | M | H | `TS-7` mandatory from phase 2 and on every tool change; corpus versioned in `P2-13` | A new tool registered without new abuse cases | Security engineer |
| R-05 | Approval and worker work compressed because it starts in W11 | M | H | Design the state machine during phase 3; keep `P4-01`…`P4-04` first in phase 4 | Phase 3 finishing later than W10 | Engineering lead |
| R-06 | Provider sandbox unavailable or behaves differently from production | M | M | Build fake and sandbox adapters against one contract test set; reconcile rather than retry blindly | Sandbox access unconfirmed at the start of phase 4 | Backend engineer |
| R-07 | Duplicate financial effect through retry after an ambiguous timeout | L | H | Idempotency key with unique constraint, atomic claim, provider state check before retry, `TS8-09`/`TS8-10` | Any retry path that does not first query provider state | Backend engineer |
| R-08 | A secret reaches a log, prompt, image, or model context | L | H | Per-service mounts, redaction rules, pipeline secret scanning, standing task `ST-05` | A scan finding, or a credential-shaped string in a log | Operations engineer |
| R-09 | OPA becomes a single point of failure and pressure grows for a local allow fallback | L | H | Deny-on-unavailable is baseline; run OPA close to the API; monitor latency; **never** add a fallback allow | Any proposal or review comment suggesting a cached allow | Security lead |
| R-10 | Cost or token abuse through an agent loop | M | M | Per-session tool, time, token, cost budgets; alerts on tool volume and spend | Rising tool-call volume per session | Onyx owner |
| R-11 | OD-01…OD-04 unanswered into phase 5; the launch gate cannot close | H | M | Monthly review; each decision has an owner and a needed-by phase; escalate at the phase 3 gate | Any decision still Open at the phase 4 gate | Product owner |
| R-12 | Year-end holidays and the W16–W17 freeze compress phase 5 | H | M | Prepare M5 evidence before the freeze, review after; no migrations or policy publication inside it | Phase 5 tasks still open entering W15 | Engineering lead |
| R-13 | A user with several roles approves an action they requested | L | H | Separation of duty enforced in **policy**, not only the portal; `TS8-03` on every phase 4 change | A policy change removing the requester check | Security lead |
| R-14 | Restored backups reactivate old approved jobs | L | H | Restore procedure verifies action states and neutralizes stale approvals; `TS9-08` proves it | A restore drill that does not inspect action state | Operations engineer |
| R-15 | Test data drifts from the fixed baseline; negative tests silently stop being negative | M | M | The seed script is the only source of test data; the names in [08 §2](08-local-build-runbook.md#2-test-data-baseline) are fixed | A test creating its own organization or user inline | Security engineer |

## 4. Launch gate tracker

Rows from [05 §12](05-verification-and-operations.md#12-launch-gate). Status moves to **Ready** only
when the named evidence exists.

| Gate | Pass condition | Evidence source | Status |
|---|---|---|---|
| Product | Approved scope, owners, roles, journeys, prohibited actions | [01](01-product-requirements.md) + OD-09 closure | Not started |
| Architecture | Data flow, trust boundaries, control-plane separation, network rules | [02](02-architecture-and-security.md) + `V-02` evidence | Not started |
| Identity | Individual authentication, MFA, token checks, service identities | `TS-1` results + OD-10 closure | Not started |
| Authorization | OPA default deny and full role/resource matrix | `TS-2` and `TS-6` results with policy version | Not started |
| Database | Least-privilege roles, RLS, backups, restoration, migration controls | `TS-3`, `TS-4`, `TS9-07` with schema version | Not started |
| Agent | Narrow tools, strict schemas, loop limits, injection tests | `TS-7` results + registered operation list | Not started |
| Actions | Approval integrity, separation of duties, idempotency, reconciliation, audit | `TS-8` results + reconciliation runbook (`P4-21`) | Not started |
| Operations | Dashboards, alerts, runbooks, on-call ownership, rollback, incident process | `TS-9` results + `P5-05`, `P5-06`, `P5-09` | Not started |
| Security assessment | Material confirmed issues fixed or formally accepted | `P5-13` findings + §5 below | Not started |

## 5. Accepted conditions

A conditional gate pass creates a row here. Empty is the correct state at project start. **No row may
exist without an owner and an expiry date.**

| ID | Condition accepted | Gate | Owner | Expiry | Removal evidence |
|---|---|---|---|---|---|
| — | *(none recorded)* | — | — | — | — |

> **Acceptance limit:** an S1 defect can never become an accepted condition. Cross-tenant exposure,
> execution without approval, duplicate financial effect, and credential exposure are fixed before a
> gate passes.

## 6. Assumption register

| ID | Assumption | Confirm by | Status | Action if broken |
|---|---|---|---|---|
| AP-01 | W01 begins 2026-09-07, five-day weeks | Phase 0 gate | Assumed | Rebaseline every milestone date |
| AP-02 | One delivery team with the listed roles | Phase 0 gate | Assumed | Extend phases 2 and 4 first; never shorten security phases |
| AP-03 | Compose is sufficient for phases 0–4 | Phase 1 gate | Assumed | Move the affected phase to integration; extend phase 0 |
| AP-04 | Model provider access in week 1 | Phase 0 gate | Assumed | Prove phase 1 through the direct API harness until access exists |
| AP-05 | Refunds use a sandbox, never a live financial system | Phase 4 gate | Assumed | Stop phase 4 execution work; escalate to security lead and product owner |
| AP-06 | A security reviewer available for every gate | Phase 1 gate | Assumed | Gates queue; the launch date moves rather than a gate being skipped |
| AP-07 | Open decisions answered by their needed-by phase | Monthly | Assumed | Apply the default or stop the dependent workstream |
| AP-08 | No gate inside the W16–W17 freeze | Phase 4 gate | Assumed | Move M5 and M6; no policy publication or migration during the freeze |

## 7. Prohibited shortcuts

These appear whenever a schedule is under pressure. Each invalidates the security baseline and every
test result produced after it. **None may be accepted as a condition at any gate.**

| Shortcut | Why it is refused |
|---|---|
| Disable RLS or grant `BYPASSRLS` to make a query work | Removes the second authorization layer protecting against application mistakes |
| Let the API own protected tables to simplify migrations | Table owners bypass row policies, so tenant isolation stops being enforced |
| Add a cached allow path when OPA is unavailable | Converts an outage into an authorization bypass |
| Accept organization or user identifiers from tool arguments | Model arguments are untrusted input |
| Register a generic SQL, shell, or HTTP tool for convenience | Gives the agent authority that cannot be tested or bounded |
| Let the API execute a refund directly to avoid building the worker | Removes the separation between request, approval, and execution |
| Let a requester approve their own action "just in the test tenant" | Separation of duty must be enforced in policy, not the interface |
| Mount the migration credential into a runtime service | A runtime compromise would grant schema, grant, and policy administration |
| Skip audit writes to improve latency | A sensitive change without evidence cannot be reconstructed or defended |

## 8. Maintenance

1. The engineering lead reviews every open decision and risk at each phase gate; changes get a new
   version number.
2. The security lead reviews accepted conditions monthly and escalates any item within two weeks of expiry.
3. A new risk is added with likelihood, impact, mitigation, early signal, and owner — or not at all.
4. A closed item keeps its identifier and evidence reference. Identifiers are never reused.
5. The launch gate tracker is updated only from stored evidence, never from a verbal report.
