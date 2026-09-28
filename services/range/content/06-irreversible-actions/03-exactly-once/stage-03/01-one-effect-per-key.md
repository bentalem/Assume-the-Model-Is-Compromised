# `one_effect_per_key`

## What your result proves

The replay was refused by `one_effect_per_key`. On its own that is ambiguous, and the ambiguity is not academic: the table could have been read-only to this role, the row could have been malformed, a grant could have been missing, a policy could have refused the insert.

The second attempt — **same table, same row shape, same role, different key** — was accepted and then removed. That eliminates all of them at once and turns "something refused it" into **"the key refused it"**.

> A refusal proves nothing until you have seen the permitted version succeed.

## Where the control lives

A unique index. That is the entire control.

```sql
-- The single most important constraint in the schema: one effect per key, whatever the worker
-- does. A retry that reaches the provider twice cannot record two successes.
CONSTRAINT one_effect_per_key UNIQUE (idempotency_key)
```

No logic, no service, nothing to get wrong at three in the morning. The database refuses the second row identically for a retry, a bug, a second worker, an operator running a script, and a job that lost its lease and came back.

Two things around it make it work:

- **The key is derived from the work, not the attempt**: the action id and its payload hash. The same work always produces the same key; different work produces a different one.
- **The key is reserved before the provider is called**, with the outcome `ambiguous`. Written after a successful call, a crash in between would leave an effect with no record. Reserved first, the worst case is a row that says *"something may have happened here"* — which is exactly what the next worker should find.

Of the three "once" constraints in the schema, only this one sits in the path of a retry. `one_decision_per_request` and `one_job_per_request` stop duplicates being *created*; in a timeout there is only ever one request, one decision and one job. The duplicate is in the attempts.

## What this check does not cover

Both attempts rolled themselves back, so there is nothing to restore.

**Idempotency makes a retry harmless. It does not tell you whether the money moved.** A row that still says `ambiguous` an hour later is a real, open question about a real payment, and resolving it means asking the provider — reconciliation, not retry. A system that retries forever and never reconciles has converted a duplicate-payment risk into a silent unresolved-state risk, which is quieter and not better.

And why the permitted attempt is on this page at all: a measurement that only ever runs against a healthy system has never exercised the path that matters. The refusal path and the success path are different code, and the one you never run is the one that runs on the day something is actually wrong — when the constraint has been dropped, or the key derivation changed.

> **A tool that is only correct when the system is correct is not an instrument.**

## Take it to a review

1. **What is your idempotency key derived from?** If a timestamp, a UUID generated per attempt, or a retry counter appears in the answer, there is no idempotency — every retry is a new operation.
2. **When is the key written — before or after the provider call?** After means a crash in between leaves an effect with no record.
3. **What happens to a call that stays ambiguous?** If the answer is "it retries", ask what eventually resolves it. Retry is not reconciliation.
4. **Is "once" enforced by a unique index, or by the code checking first?** A check-then-insert is a race with itself the moment there are two workers.

Question 4 is the one that finds things, and it generalises past this topic: **a rule enforced by looking before acting is a rule that two actors can break simultaneously.** The constraint does not have that problem, because the database is the thing doing both.
