# The timeout

Your worker calls the payment provider. Thirty seconds later the connection times out.

**Did the money move?**

You do not know. Three things are equally consistent with what you observed:

1. The request never arrived. Nothing happened.
2. The request arrived, the refund was issued, and the **response** was lost.
3. The request arrived and is still being processed.

And the decision you have to make right now is whether to retry.

- **Retry, and it was case 2** → you have refunded twice.
- **Do not retry, and it was case 1** → the customer is still waiting, and eventually somebody
  refunds manually. Possibly twice.

There is no answer that is safe *by itself*. This is not a hard problem because people are careless;
it is hard because the information genuinely is not there.

## So stop trying to know

The whole trick is to give up on finding out what happened, and instead make **the second attempt
harmless**.

> **Idempotency: performing the same operation twice has the same effect as performing it once.**

If that holds, the timeout stops being a dilemma. Retry. Retry ten times. If the first call landed,
the rest change nothing.

## How it is actually built

A key, derived from the identity of the work rather than from the attempt:

```python
def idempotency_key(action_id: str, hash_value: str) -> str:
    return f"{action_id}:{hash_value[:32]}"
```

Two properties, both load-bearing:

- **The same work produces the same key**, every time, on any worker, after any restart. It is
  derived from the action and its payload hash — not from a timestamp, a random value, or an attempt
  counter, any of which would produce a fresh key per retry and defeat the whole thing.
- **Different work produces a different key.** A second, genuinely different refund on the same
  order has a different payload, so a different hash, so a different key.

Then the key is reserved in the database **before the provider is called**, with the outcome
`ambiguous`. Read that again — before, not after:

```
INSERT ... (idempotency_key, outcome) VALUES (key, 'ambiguous')
```

If you write the row after a successful call, a crash between the call and the write leaves no
record of an effect that happened. Reserving first means the worst case is a row that says
*"something may have happened here"* — which is exactly what you want a subsequent worker to find.

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
