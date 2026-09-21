# The three constraints

## The three "once" constraints in this schema

| Constraint | Stops |
|---|---|
| `one_decision_per_request` | a second approval on one request |
| `one_job_per_request` | a second job for one request |
| **`one_effect_per_key`** | **a second effect recorded under one key** |

The first two prevent duplicates from being *created*, and they are useful. Neither helps with the
timeout, because in the timeout there is only ever one request, one approval and one job — **the
duplicate is in the attempts, not in the records above them.**

Only the third is in the path of a retry. Its comment in the schema calls it the most important
constraint in the file, and the reason is that it holds no matter what the worker does: a worker
with a bug, a worker started twice, a worker that lost its lease and came back — all of them meet
the same unique index.

## And the part that is not automatic

Idempotency makes retrying safe. It does **not** tell you whether the money moved.

A row that still says `ambiguous` an hour later is a real, open question about a real payment, and
resolving it means asking the provider — reconciliation, not retry. A system that retries forever
and never reconciles has converted a duplicate-payment risk into a silent unresolved-state risk,
which is quieter and not better.

> **Never blind-retry.** Retry under the same key, and reconcile what stays ambiguous.
