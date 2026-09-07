# Documentation index

## Reading order

**Before writing any code:** [CLAUDE.md](../CLAUDE.md) → [01-product-requirements.md](01-product-requirements.md)
→ [02-architecture-and-security.md](02-architecture-and-security.md) → [03-data-identity-authorization.md](03-data-identity-authorization.md).

**To start building:** [06-action-plan.md](06-action-plan.md) for the phase you are in →
[07-task-backlog.md](07-task-backlog.md) for the task → [08-local-build-runbook.md](08-local-build-runbook.md)
for the exact steps → the relevant file in [../specs/](../specs/) for the contract.

**To close a task:** [09-test-plan.md](09-test-plan.md) for the tests that must pass and the evidence
they must produce.

## The documents

### Baseline design (what was agreed — change only through review)

| File | Source doc | Contents |
|---|---|---|
| [01-product-requirements.md](01-product-requirements.md) | SP-PRD-001 | Roles, scope, tools, journeys, functional requirements, success criteria |
| [02-architecture-and-security.md](02-architecture-and-security.md) | SP-ARCH-001 | Components, trust boundaries, read and action flows, threat model, failure behavior |
| [03-data-identity-authorization.md](03-data-identity-authorization.md) | SP-DATA-001 | Identity, tokens, authorization model, database roles, RLS, audit, secrets |
| [04-build-and-deployment.md](04-build-and-deployment.md) | SP-BUILD-001 | Build phases, repo layout, configuration, Onyx and OPA integration, pipeline |
| [05-verification-and-operations.md](05-verification-and-operations.md) | SP-OPS-001 | Test matrix, monitoring, runbooks, change management, launch gate |

### Delivery plan (how and when — updated as work proceeds)

| File | Source doc | Contents |
|---|---|---|
| [06-action-plan.md](06-action-plan.md) | SP-PLAN-001 | Workstreams, phases, milestones, critical path, gate procedure |
| [07-task-backlog.md](07-task-backlog.md) | SP-PLAN-002 | Every task with dependency and closing evidence — **the working tracker** |
| [08-local-build-runbook.md](08-local-build-runbook.md) | SP-PLAN-003 | Ordered build steps and the `V-01`–`V-12` verification checks |
| [09-test-plan.md](09-test-plan.md) | SP-PLAN-004 | Suites `TS-1`–`TS-10`, phase assignment, defect handling |
| [10-risk-and-decisions.md](10-risk-and-decisions.md) | SP-PLAN-005 | Open decisions, risks, launch gate tracker, prohibited shortcuts |

### Implementation contracts (what the code must match)

| File | Contents |
|---|---|
| [../specs/database-schema.md](../specs/database-schema.md) | DDL, roles, grants, RLS policies, migration order |
| [../specs/api-contract.md](../specs/api-contract.md) | Endpoints, schemas, error model, request pipeline |
| [../specs/policy-contract.md](../specs/policy-contract.md) | OPA input and output shape, rules, reason codes, tests |

## Identifier conventions

| Prefix | Meaning | Defined in |
|---|---|---|
| `FR-nn` | Functional requirement | 01 |
| `P<phase>-nn` | Build task | 07 |
| `V-nn` | Local environment verification check | 08 |
| `T-nnn` | Core test case | 05 |
| `TS<n>-nn` | Test case inside suite `TS-n` | 09 |
| `OD-nn` | Open decision | 10 |
| `R-nn` | Risk | 10 |
| `AP-nn` | Planning assumption | 06 / 10 |

## Where the authoritative copy lives

The `.docx` files in the project root are the signed baseline and the formal plan. This Markdown is
the working copy the build follows. If they disagree, the `.docx` wins on *what was agreed* and this
Markdown wins on *what the code currently does* — and that disagreement is itself a defect to fix.
