# Complete, or not at all

The decision chain for alice's forget:

1. **Find the record** under row-level security. Not hers, or already forgotten: not found.
2. **Read `forget.scope`** — in the same transaction, so the scope cannot change halfway.
3. **Walk the derivation tree** (scope `all`): the record and everything derived from it, at any depth.
4. **Forget every record** through `mem.forget_records`. A plain `UPDATE ... SET deleted_at` is refused by row-level security: the updated row would no longer pass the read policy. The function runs with the caller's own context, so it can only forget what the caller could see.
5. **Queue a delete for each** in the outbox, in the same transaction, and apply them to both vector layouts after commit.

With scope `primary`, steps 3 and 5 are skipped. The record goes; its summary and every vector stay.

## Why the restore re-runs memory-init

Setting the scope back to `all` makes the next forget complete. The half-done ones stay half done —
the surviving summary is still live and still in alice's context. So the Range's restore also runs
memory-init, which, only now that the setting says forgetting is complete, forgets every live record
derived from a forgotten one and removes every vector whose record is not live. While the setting is
armed it leaves them alone on purpose: they are what the reconciliation check exists to name.

## The reconciliation check

`supportpilot-memory-reconcile` compares memory-db with both vector layouts and names every
disagreement — a point for a record that is not live, a live record with no point, a hash that does
not match. It is `V-29` in `verify_local.py`. A deletion you cannot verify is a deletion you are
taking on trust.
