# 06 — Action plan

> Source: `06_SupportPilot_Master_Action_Plan.docx` (SP-PLAN-001 v1.0, 2026-09-07)

**Planning rule:** a phase is complete only when its positive and negative authorization tests pass
and its evidence is stored. A working chat response is never a completion signal.

## 1. Assumptions

| ID | Assumption | Effect if wrong |
|---|---|---|
| AP-01 | Week 1 begins Monday 2026-09-07; a week is five working days | All milestone dates shift equally |
| AP-02 | One delivery team with the roles in §6 | Phases 2 and 4 extend first |
| AP-03 | Docker Compose is enough for phases 0–4 | Phase 0 grows; phase 1 starts later |
| AP-04 | Model provider access available in week 1 | Phase 1 cannot be demonstrated end to end on time |
| AP-05 | Refunds use a provider sandbox, never a live financial system | Phase 4 needs formal risk acceptance |
| AP-06 | A security reviewer is available for each gate | Gates queue; launch moves |
| AP-07 | Open decisions are answered by their needed-by phase | The dependent workstream stops |
| AP-08 | Weeks 16–17 contain holidays; no gate inside a freeze | Phase 5 finishes later |

## 2. Workstreams

| ID | Workstream | Owns |
|---|---|---|
| WS-A | Platform and environment | Repository, images, networks, secret mounts, health checks, bootstrap |
| WS-B | Identity | Keycloak realm, clients, users, groups, MFA, token verification |
| WS-C | Authorization policy | OPA bundle, input contract, reason codes, policy tests, publication |
| WS-D | Data and database | Schema, roles, grants, RLS, migrations, seeds, database tests |
| WS-E | API and tools | Tool endpoints, schemas, resource lookup, response minimization, audit |
| WS-F | Agent integration | OpenAPI document, Onyx action and agent config, loop and cost budgets |
| WS-G | Actions, approval, worker | State machine, approval portal, worker, adapters, idempotency |
| WS-H | Security verification | Test matrix, abuse cases, tenant isolation, evidence capture |
| WS-I | Operations and release | Pipeline, monitoring, runbooks, backup/restore, change control |

## 3. Phases

| Phase | Name | Weeks | Lead WS | Exit evidence |
|---|---|---|---|---|
| 0 | Project baseline | W01–W02 | A | Environment starts and verifies from a clean machine |
| 1 | Identity and one protected read | W03–W05 | B, C, D, E, F | T-001…T-007 pass, incl. cross-tenant denial at both layers |
| 2 | Complete read capabilities | W06–W08 | E, C, D, F, H | T-008, T-014 pass; stored injections change nothing |
| 3 | Controlled low-impact writes | W09–W10 | E, D, C | Write tests pass, incl. stale-state and cross-tenant denial |
| 4 | Approval and worker | W11–W14 | G, C, D, E, H | T-009…T-013 pass; no effect before approval, none twice |
| 5 | Hardening and operational readiness | W15–W18 | I, A, H | All launch gate rows pass or formally accepted |

**Entry criteria** for each phase: the previous phase's gate passed. Phase 1 also needs the realm
design and `get_order` schema reviewed; phase 4 needs the approval rule, separation-of-duty rule, and
provider sandbox confirmed; phase 5 needs the production platform and secret manager selected.

## 4. Milestones

| ID | Milestone | Target | Pass condition |
|---|---|---|---|
| M0 | Environment baseline accepted | 2026-09-18 | Clean machine → verified environment with one command |
| M1 | First protected read proven | 2026-10-09 | Alice reads a Cedar order; Northwind returns no protected data |
| M2 | Read surface complete | 2026-10-30 | Minimized fields, pagination, audit events, injection tests pass |
| M3 | Controlled write proven | 2026-11-13 | Notes created with server-derived authorship and full audit |
| M4 | Approval and execution proven | 2026-12-11 | Propose → independent approve → single execution → reconciliation |
| M5 | Operational readiness complete | 2027-01-08 | Monitoring, runbooks, restore test, scans, assessment results |
| M6 | Launch gate decision | 2027-01-15 | Every gate row pass or accepted risk with owner and expiry |

> **Freeze note:** weeks 16–17 include holidays and a change freeze. No gate, migration, or policy
> publication inside the freeze; M5 evidence is prepared before it and reviewed after it.

## 5. Critical path

```
networks/compose → Keycloak realm → API token verification ─┐
                                                            ├→ OPA decision call → read tools
core schema + seeds → trusted resource lookup ──────────────┘        ↑
migration role separation → runtime roles → RLS policies ────────────┘
read tools → Onyx action registration → audit events → action state machine
           → approval portal → worker execution → operational readiness
```

Each arrow is a hard dependency; delay moves the launch gate one week for one week.

| Step | Why the order cannot change |
|---|---|
| Realm before token verification | Cannot test verification without a running issuer |
| Token verification before everything | Every later decision needs a verified subject |
| Resource lookup before OPA | Policy input must contain server-side attributes |
| Migration role before RLS | Runtime roles must not own protected tables |
| Both authorization layers before tools | A tool must not exist before both apply to it |
| Tools before Onyx registration | The model may call only operations that already enforce authorization |
| Action state machine before approval | Approval binds to an immutable stored payload hash |
| Approval + idempotency before worker | Execution requires valid approval and a duplication guard |

## 6. Ownership

Replace each role with a named person before baselining — an unnamed owner is open item **OD-09**.

| Workstream | Responsible | Accountable | Consulted |
|---|---|---|---|
| WS-A Platform | Platform engineer | Engineering lead | Security engineer |
| WS-B Identity | Identity engineer | Security lead | Platform engineer, Onyx owner |
| WS-C Policy | Policy engineer | Security lead | Backend engineer, Product owner |
| WS-D Database | Database engineer | Engineering lead | Security engineer |
| WS-E API and tools | Backend engineer | Engineering lead | Policy engineer, Product owner |
| WS-F Agent integration | Onyx owner | Product owner | Backend engineer, Security engineer |
| WS-G Actions and worker | Backend engineer | Engineering lead | Finance approver, Security lead |
| WS-H Verification | Security engineer | Security lead | All engineers |
| WS-I Operations | Operations engineer | Operations lead | Security lead, Engineering lead |

## 7. Cadence

- **Daily** — delivery sync on blocked tasks and gate risk.
- **Weekly** — security review of new tools, schemas, policies, prompts *before* merge; backlog grooming.
- **Per phase** — gate review with the evidence package.
- **Per control-plane change** — review per [05-verification-and-operations.md](05-verification-and-operations.md#10-change-management), regardless of phase.
- **Monthly** — risk register review, including expiry of accepted risks.

## 8. Phase gate procedure

1. Workstream leads confirm every task for the phase is closed or formally deferred.
2. The test owner runs the phase test set and attaches results, including negative cases.
3. The security engineer confirms threat-model updates and that no new authority was granted to the
   model or a runtime service.
4. The database engineer confirms grants, RLS, and migration version.
5. The evidence package is stored with source revision, image digests, policy version, schema version.
6. Engineering lead and security lead record **pass**, **conditional pass** (owner + date), or **fail**.
7. A conditional pass creates a tracked item in [10-risk-and-decisions.md](10-risk-and-decisions.md#5-accepted-conditions)
   with an expiry date. Silent deferral is not allowed.

## 9. Escalation

| Trigger | Action | Decision owner |
|---|---|---|
| A phase exit test fails twice on the same control | Stop new feature work in that workstream; fix and add a regression test | Security lead |
| An open decision passes its needed-by phase | Apply the recorded default or stop the workstream; do not improvise | Product owner |
| A milestone slips more than a week | Rebaseline following milestones; never compress a security phase | Engineering lead |
| A control-plane boundary would be weakened to meet a date | Reject and escalate; the boundary is baseline, not scope | Security lead |
| Provider sandbox unavailable in phase 4 | Continue with the fake adapter; record an open launch-gate condition | Product owner |
