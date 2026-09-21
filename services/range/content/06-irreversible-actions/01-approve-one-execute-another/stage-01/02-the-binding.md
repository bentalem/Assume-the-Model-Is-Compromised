# The binding

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
