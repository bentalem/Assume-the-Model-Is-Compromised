# The refusal

## What your result proves

`payload_hash_mismatch_stored`.

```python
recomputed = payload_hash(job.payload)
if recomputed != job.payload_hash:
    raise RefusedToExecute("payload_hash_mismatch_stored")
if decision["approved_hash"] != job.payload_hash:
    raise RefusedToExecute("payload_hash_mismatch_approved")
```

You changed the payload and left the hash. The worker hashes what it is **about to send**, compares it to what the request claims, and stops before the provider is called.

The second check would not fire, and that is informative: the approval still matches the *stored* hash perfectly, because you never touched either of them. **The approval is entirely valid. It is just about different content.**

| Reason code | What happened | Who did it |
|---|---|---|
| `payload_hash_mismatch_stored` | the payload was edited after proposal | anyone with write access to the request |
| `payload_hash_mismatch_approved` | the approval does not belong to this payload | an approval replayed, or recorded against the wrong request |

A system with only the second would have executed your 4500.00 without hesitation: the approval and the stored hash agree, and nobody asked what the payload actually says now.

## Where the control lives

**In the worker, in the last component before the irreversible act.** Not in the API. Not in the portal. The worker is the only place that knows the payload it is actually about to send; every check upstream of it is a check on a payload that something downstream might still change — and moving this one earlier reintroduces the gap it closes.

> **The stored hash is a claim. The recomputed hash is a measurement.** Controls that compare two claims to each other are the ones that quietly stop working.

The approval row stores the hash a second time (`approved_hash`, migration `0008`) for the same reason. If the approval merely pointed at the request, anything that could update the request's `payload_hash` would retroactively change what the approver approved. Storing it again makes the approval a statement about specific content, made at a specific time.

## What restoring fixes

Restoring puts the amount back to 45.00, and the payload matches its hash again.

Be precise about what you observed. Nothing reached the worker in this challenge: the request is still `PENDING_APPROVAL`, so no job exists. You established the reason code by matching the state you created against the worker's checks, read from its source — which is exactly how you would reason about a system you cannot run. What you did to get there is the threat model: you edited a row directly, with no API, no portal and no policy engine. The paths that skip the application are the ordinary ones — a migration, a support script, a fix during an incident — and that is why this check sits downstream of every one of them.

## Take it to a review

1. **When someone approves, what exactly do they approve?** If the answer names a record rather than a content, ask what stops that record changing.
2. **Is the binding recomputed at execution, or compared to a stored value?** This is the question. Most systems do the second and believe they do the first.
3. **Show me the refusal.** Change a payload after approval and watch it be refused. If nobody has done that, nobody knows whether the check runs.

The third one is the lab's own rule again: a control nobody has watched fail is a control being trusted.

> Put the integrity check at the boundary of the irreversible act, not at the boundary of the request that asked for it.

**Reset before you leave.** Until you do, the pending payload says 4500.00, and the next thing you measure will be measuring that.
