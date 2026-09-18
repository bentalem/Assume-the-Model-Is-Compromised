# SupportPilot

**A lab for learning how to secure AI agents — by breaking a real one.**

SupportPilot is a working multi-tenant AI support agent: Onyx running the agent loop, Keycloak for
identity, a FastAPI service exposing seven tools, Open Policy Agent for the rules, PostgreSQL with
row-level security for the data, and a separate worker as the only component that can execute a
refund.

It is not a demo of an agent. It is a system built so that **every control can be removed and the
resulting failure observed.**

> **The core rule:** the model may *propose* tool use. Trusted services decide what is allowed, and
> trusted services perform every real action.

---

## Why this exists

Most agent-security material is about the model: better prompts, guardrails, injection filters. This
lab starts from the opposite assumption.

> **The model is not the thing you secure. The model is the thing you assume is compromised.**

Assume it will, at some point, do exactly what an attacker wants. One question is left — **what can
it reach?** That question has engineering answers, and you can run all of them here.

The lab is for the people who already know this work: whoever owns authorization, identity and data
access, and who has usually not been invited to the agent project.

---

## Start here

```bash
git clone <this repo>
cd supportpilot
./scripts/bootstrap-local.ps1     # builds images, applies migrations, seeds the tenants
./scripts/verify-local.ps1        # 16 checks, V-01 … V-16, every one must pass
```

Full steps, prerequisites and troubleshooting: [`docs/08-local-build-runbook.md`](docs/08-local-build-runbook.md).
Connecting Onyx so a real model drives the tools: [`docs/runbooks/onyx-integration.md`](docs/runbooks/onyx-integration.md).

> **Safety rule:** this environment holds realistic **non-production** records only. Never load real
> customer data, real payment credentials, or a production dump.

---

## What you get

Two tenants that must never see each other. Five users with different roles. Seven tools. One ticket
carrying ten injection attempts written to look like ordinary customer messages.

| | Cedar | Northwind |
|---|---|---|
| Users | `alice` agent · `bob` manager · `fiona` approver · `dana` auditor | `mallory` agent |
| Orders | `ORD-2001` · `ORD-2002` · `ORD-2003` | `ORD-3001` |
| Customers | `CUS-4001` · `CUS-4002` · `CUS-4003` *(restricted)* | `CUS-9001` |
| Tickets | `TKT-1001` *(10 injections)* | `TKT-3001` |

Three fixtures carry most of the lessons. `ORD-3001` is the order Alice must never read, however she
asks. `CUS-4003` is the record an agent gets *without* the email address and a manager gets with it —
because policy returns a field list and the API drops the rest. `TKT-1001` is the ticket that tries
to talk the agent into everything.

---

## Where to start breaking it

The fastest way to understand a control is to remove it and watch what happens. Roughly in order of
how much each one teaches:

1. **Stop OPA**, then read an order you are fully entitled to read. You should get `503` and no data.
   If you get the order, something has a fallback.
2. **Point the API at the migration role** instead of `sp_api_role`. The row policies are still
   there, still correct, and now filtering nothing.
3. **Drop `FORCE`** from one table's row-level security and read across tenants.
4. **Ask the agent for fifteen customer searches** in one message. Every call will be authenticated,
   authorised, correctly tenant-scoped and correctly logged — and you will have the directory.
5. **Approve a refund, then change the amount** in the database before the worker claims it. The
   hash check should refuse it twice over.
6. **Give the agent a service-account token** instead of the user's own. Then ask, as Alice, for
   `ORD-3001`.

The last one changes a single header value and changes everything.

---

## Proving it works

Nothing here is trusted because it was designed carefully. Every control has a check that fails
loudly when it stops working.

| Suite | What it proves |
|---|---|
| `scripts/verify_local.py` | 16 environment checks, `V-01`…`V-16` |
| `scripts/abuse_suite.py` | injection and abuse cases, `TS7-nn` |
| `scripts/action_suite.py` | approval and execution cases, `TS8-nn` |
| `scripts/contract_suite.py` | every call built from the published tool document |
| `policy/tests/` | the Rego rules, including every deny arm — `opa test policy/` |
| `services/api/tests/` | token, policy client, pipeline, hashing, pagination — `pytest services/api` |

`contract_suite.py` exists because of a real failure. One tool declared an array query parameter,
Onyx serialised it one way, the API expected another, and a perfectly correct model request came back
as an error — while 219 tests passed throughout, because every one of them built its own URL.

> **A test that constructs the request is testing your assumptions, not your system.**

---

## Reading order

| Start with | For |
|---|---|
| [`docs/architecture/`](docs/architecture/) | How the system fits together — diagrams, trust boundaries, the request pipeline |
| [`README.md`](README.md) | *Assume the Model Is Compromised* — the write-up this lab was built to support |
| [`docs/learning/00-curriculum.md`](docs/learning/00-curriculum.md) | The training track: eleven modules, in order |
| [`docs/learning/handbook.md`](docs/learning/handbook.md) | The field manual — principles, mechanisms, the question bank, the failures |
| [`docs/08-local-build-runbook.md`](docs/08-local-build-runbook.md) | Empty machine → a proven authorized read |
| [`specs/`](specs/) | The exact contracts: database schema, API, policy |
| [`CLAUDE.md`](CLAUDE.md) | The invariants — what must never be weakened to make something work |

---

## Repository map

```
compose.yaml              four networks, seven services
services/
  api/                    auth · policy · tools · repositories · audit
  worker/                 jobs · adapters · idempotency
  approval-portal/        renders a payload hash, forwards a decision
database/
  migrations/             schema, roles, grants, RLS — owned by sp_migrator_role
  seeds/                  the two tenants and the injection corpus
policy/supportpilot/      authz.rego + limits.json
policy/tests/             53 policy tests
openapi/                  the registered action set, for Onyx
infrastructure/local/     Keycloak realm, Onyx compose overlay
scripts/                  bootstrap, verify, the four suites, the learning exercises
docs/                     architecture · article · learning · runbooks · decisions
specs/                    implementation contracts
```

---

## What this lab deliberately is not

No autonomous refunds without approval. No free-form SQL generated by the model. No general shell,
file-system or cloud-administration tool. No model training or fine-tuning. And no production
deployment: this is Compose on one machine, holding invented data, built to be attacked.
