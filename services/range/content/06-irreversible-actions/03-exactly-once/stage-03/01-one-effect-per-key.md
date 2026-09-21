# `one_effect_per_key`

A unique index. That is the entire control.

```sql
-- The single most important constraint in the schema: one effect per key, whatever the worker
-- does. A retry that reaches the provider twice cannot record two successes.
CONSTRAINT one_effect_per_key UNIQUE (idempotency_key)
```

No logic, no service, nothing to get wrong at three in the morning. The database refuses the second
row, and it refuses it identically for a retry, a bug, a second worker, an operator running a script,
and a job that lost its lease and came back.

## Why the control group mattered

The replay was refused. On its own that is ambiguous, and the ambiguity is not academic: the table
could have been read-only to this role, the row could have been malformed, a grant could have been
missing, a policy could have refused the insert.

The second attempt — **same table, same row shape, same role, different key** — was accepted and then
removed. That eliminates all of them at once and turns "something refused it" into **"the key
refused it"**.

> A refusal proves nothing until you have seen the permitted version succeed.

The same discipline as 6.2, and it is the habit worth taking out of this track more than any
individual control.

## Why the permitted attempt is on this page at all

It would be tidier to show you only the refusal. It would also be worthless.

A measurement that only ever runs against a healthy system has never exercised the path that
matters. The refusal path and the success path are different code, and the one you never run is the
one that runs on the day something is actually wrong — when the constraint has been dropped, when
the key derivation changed, when the row was written by an older version of the worker.

> **A tool that is only correct when the system is correct is not an instrument.**

That is why every challenge here gives you the unarmed run first, and why "it refused" is not a
result until you have seen the same instrument report a success.

## What to ask a client

1. **What is your idempotency key derived from?** If a timestamp, a UUID generated per attempt, or a
   retry counter appears in the answer, there is no idempotency — every retry is a new operation.
2. **When is the key written — before or after the provider call?** After means a crash in between
   leaves an effect with no record.
3. **What happens to a call that stays ambiguous?** If the answer is "it retries", ask what
   eventually resolves it. Retry is not reconciliation.
4. **Is "once" enforced by a unique index, or by the code checking first?** A check-then-insert is a
   race with itself the moment there are two workers.

Question 4 is the one that finds things, and it generalises past this topic: **a rule enforced by
looking before acting is a rule that two actors can break simultaneously.** The constraint does not
have that problem, because the database is the thing doing both.
