# How it is built

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
