# What exactly was approved?

Somebody says *"the refund was approved"*. Ask what that sentence is about.

**"A refund"?** Then it is a category, and an approval of a category is a standing permission to
issue refunds — which nobody intends and everybody implements.

**"That refund"?** Then something has to pin down *which*, and pin it down in a way that cannot
drift between the moment of approval and the moment of execution. Those two moments are seconds
apart in the happy case and hours apart in the interesting one.

> **Approving an action is not a control. Approving a payload is.**

## Time of check, time of use

The gap is the oldest shape in security. A value is checked, and then used, and something happens in
between.

```
09:14:02   propose    amount 45.00
09:14:40   approve    "yes, 45.00 is reasonable"
09:14:41   ...
09:18:33   execute    amount ????
```

If the thing that executes reads the amount fresh from a row that anyone could have updated, the
approval covered a number that no longer exists. Nobody forged an approval. The approval is genuine,
recorded, attributable — and it is about a different payload.

## The binding

The fix is to make the approval bind to **the content**, not to the record:

1. At proposal, the server canonicalises the payload and stores `sha256` of it as `payload_hash`.
2. The approver approves, and the approval records `approved_hash` — **a second copy** of that
   hash, stored on the approval row itself.
3. At execution the worker **recomputes** the hash from the payload it is about to send, and refuses
   unless it matches both.

Step 3 is the one that matters. A check at approval time proves the approver saw the right number. A
recomputation at execution time proves nothing changed since.

## Why the approval stores the hash a second time

It looks redundant — the hash is already on the request. The source panel in Stage 03 has the
comment, and the reasoning is worth having:

If the approval merely pointed at the request, then anything that could update the request's
`payload_hash` would retroactively change what the approver approved, and the record would say the
approver approved the new value. Storing it again makes the approval **a statement about a specific
content**, made at a specific time, that cannot be edited by changing something else.

That is the difference between a record of a decision and a pointer to whatever is current.

## What the worker checks, and in what order

Two comparisons, two distinct reason codes:

| Comparison | Fires when | Means |
|---|---|---|
| recomputed hash ≠ stored `payload_hash` | the payload was altered after proposal | the request itself was tampered with |
| `approved_hash` ≠ stored `payload_hash` | the approval is for different content | the approval does not cover this request |

The first catches what you are about to do. The second catches an approval moved, replayed, or
recorded against the wrong request.

**Both exist because they fail differently**, and a system with only the second would accept a payload
edited by anyone who could also leave the approval alone — which is the easier of the two attacks.

## And one thing the console cannot do

The observation in Stage 02 will show you the amount and the hash. It will **not** tell you the hash
no longer matches, and that is deliberate: recomputing it here would mean reimplementing the worker's
canonicalisation, and a reimplementation that disagreed about key order would report a mismatch for
the wrong reason.

An instrument that says "tampering detected" because of a bug in the instrument is worse than one
that says less. So this one says less, and the recomputation stays in the worker — where you can read
it.
