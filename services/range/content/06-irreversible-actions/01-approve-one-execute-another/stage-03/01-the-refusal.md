# The refusal

`payload_hash_mismatch_stored`.

```python
recomputed = payload_hash(job.payload)
if recomputed != job.payload_hash:
    raise RefusedToExecute("payload_hash_mismatch_stored")
if decision["approved_hash"] != job.payload_hash:
    raise RefusedToExecute("payload_hash_mismatch_approved")
```

You changed the payload and left the hash. The worker hashes what it is **about to send**, compares
it to what the request claims, and stops before the provider is called.

The second check did not fire, and that is informative: the approval still matches the *stored* hash
perfectly, because you never touched either of them. **The approval is entirely valid. It is just
about different content.**

## The two failures are not the same failure

| Reason code | What happened | Who did it |
|---|---|---|
| `payload_hash_mismatch_stored` | the payload was edited after proposal | anyone with write access to the request |
| `payload_hash_mismatch_approved` | the approval does not belong to this payload | an approval replayed, or recorded against the wrong request |

A system with only the second would have executed your 4500.00 without hesitation: the approval and
the stored hash agree, and nobody asked what the payload actually says now.

That is the whole argument for recomputing at execution rather than trusting a stored value. **The
stored hash is a claim. The recomputed hash is a measurement.** Controls that compare two claims to
each other are the ones that quietly stop working.

## Where the check has to live

Not in the API. Not in the portal. **In the last component before the irreversible thing happens.**

The worker is the only place that knows the payload it is actually about to send. Every check
upstream of it is a check on a payload that something downstream might still change — and if you
move this one earlier, you have reintroduced the gap you closed.

> Put the integrity check at the boundary of the irreversible act, not at the boundary of the
> request that asked for it.

## What to ask a client

1. **When someone approves, what exactly do they approve?** If the answer names a record rather than
   a content, ask what stops that record changing.
2. **Is the binding recomputed at execution, or compared to a stored value?** This is the question.
   Most systems do the second and believe they do the first.
3. **Show me the refusal.** Change a payload after approval and watch it be refused. If nobody has
   done that, nobody knows whether the check runs.

The third one is the lab's own rule again: a control nobody has watched fail is a control being
trusted.

## A note on how you did it

You edited a row in the database — no API, no portal, no policy engine. That is not cheating; it is
the threat model. The paths that skip the application are the ones that skip the application's
checks, and they are the ordinary ones: a migration, a support script, a fix during an incident.

Which is exactly why this check is in the worker and not upstream. It is downstream of every path.

**Reset before you leave.** The payload is currently 4500.00, and a lab left in that state will
confuse the next thing you measure.
