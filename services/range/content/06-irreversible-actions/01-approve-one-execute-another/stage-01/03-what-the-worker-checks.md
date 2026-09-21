# What the worker checks

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

## And one thing it can do instead

Reading is not recomputing. The third button in the console lists every refusal in the worker's
`verify()` — the condition, the reason code it raises, and the line it sits on — taken from the
worker's source at the moment you press it, not from a list somebody typed into the Range and hoped
stayed true.

It is bounded the same way the observation above is. It does not evaluate a single one of those
conditions, so it cannot be wrong about which one fired; it has no opinion about the lab's state at
all. What it gives you is the worker's **vocabulary**.

Which leaves the part that is the actual exercise. The list has seven entries. The lab is in exactly
one state, and you put it there. Work out which condition your arming made true — the observations
above tell you that — and the code is on the same row.
