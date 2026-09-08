# Agent security consulting — training track

The goal is not to build SupportPilot. It is to be the person an organization hires to sit beside
the team building their agent and say where they are wrong, before it costs them.

SupportPilot is the case study: a system where every control is already implemented and provable, so
each module can point at a real enforcement point rather than a principle.

## The one idea (module 0)

The model is **untrusted input** — the same status as a form field filled in by an anonymous user.
Not an untrusted component: untrusted *input*.

From which the only test that matters:

> **If a rule can only be stated inside the prompt, it is not a control. It is a request.**

Carry it into every meeting. For any control someone shows you, ask: *who enforces this when the
model decides to ignore it?* If the answer is "the model", you have found a finding.

## Modules

| # | Module | What you hand the client | Reference |
|---|---|---|---|
| 0 | The one idea | — | — |
| 1 | Scoping the mandate | Scope and prohibited actions | [01](../01-product-requirements.md) |
| 2 | Threat modelling an agent | Threat model | [02 §9](../02-architecture-and-security.md#9-threat-model) |
| 3 | Identity and authorization | Authorization model review | [03](../03-data-identity-authorization.md) |
| 4 | **Tool authority review** | Blast-radius report per tool | [api-contract](../../specs/api-contract.md) |
| 5 | High-impact actions | propose/approve/execute review | [02 §7](../02-architecture-and-security.md#7-sensitive-action-flow) |
| 6 | Proving it | Verification plan and evidence package | [09](../09-test-plan.md) |
| 7 | Operating and change control | Runbooks, monitoring, change gates | [05 §7–10](../05-verification-and-operations.md) |
| 8 | The consulting layer | Findings, gates, risk acceptance | [10](../10-risk-and-decisions.md) |

Module 4 is the one that distinguishes the role. Reading a tool schema and saying "that is more
authority than this job needs" is what the client is paying for, and few people do it well.

## How each module runs

1. The principle, and the failure it prevents.
2. The question you ask the client.
3. The wrong answer you will hear, and why it sounds right.
4. SupportPilot as the worked example — real code, not a diagram.
5. An exercise: you decide, and the decision gets attacked.
6. The evidence that settles it.

In exercises Claude plays the client: one with a deadline, a working system, and a reason why each
control is unnecessary. That resistance is the part of the job that cannot be learned from reading.

## Progress

| Module | State | Notes |
|---|---|---|
| 0 | done | The trust boundary and the prompt test |
| 1 | in progress | Meridian Retail engagement |
| 2–8 | not started | |
