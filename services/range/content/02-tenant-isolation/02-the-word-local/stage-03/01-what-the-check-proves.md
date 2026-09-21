# What the check proves, and how it manages to

The check is short enough to hold in your head:

```
for _ in range(6):
    api_get(CEDAR_ORDER, alice)
    api_get(NORTHWIND_ORDER, alice)

count = psql("SELECT count(*) FROM app.orders", "sp_api_role")
if count != "0":
    raise CheckFailed(...)
```

Three decisions in it, and each one is doing work.

**Twelve requests, not one.** A pool hands out whatever connection is free. One request proves
nothing — it might get a fresh connection every time. Twelve alternating requests make reuse close
to certain, which is what turns "probably fine" into evidence.

**Two tenants, alternating.** If context did survive a request, the next request would inherit the
*wrong* tenant rather than its own, so any leak shows up as data crossing a boundary rather than as
a harmless repeat.

**The final question is asked with no context at all.** This is the part worth stealing. It connects
as `sp_api_role`, sets nothing, and counts rows. Under row-level security with no
`app.organization_id` established, the correct answer is **zero** — every policy fails closed
because the tenant condition cannot be satisfied.

So a non-zero count means a connection still had context on it from an earlier request. The test
does not look for the leak in a response body, where it would be hard to see; it asks the database
directly, in the one state where the answer can only be zero.

> **A test for leaked context has to ask a question that can only be answered by leaked context.**
> Anything else is measuring the happy path twice.

## What it does not prove

Be precise, because the check is good and the claim around it can still be too large.

- It does not prove the pool reused a connection — it makes it overwhelmingly likely, not certain.
- It does not prove the *cleanup* path works, only that nothing survived. `SET LOCAL` unwinding and
  an explicit reset would both pass this.
- It says nothing about the worker, which has its own connections.

That is fine. A check should be named for what it establishes, and this one is: *pooled connections
retain no request context between requests.* It does not claim the mechanism, only the outcome —
which is the right way round, because the outcome is what you actually need to be true.

## The defence in depth underneath it

Even with the word removed, this system would not necessarily leak, and it is worth knowing why
before writing the finding.

Request 2 sets its own context before querying, so it would overwrite the stale values rather than
inherit them. The leak needs a second condition: a request that queries **without** setting context
first — a health check, a background read, an endpoint someone added in a hurry, a code path where
the context helper was forgotten.

So the real shape of the bug is: `SET` leaves a loaded gun on the connection, and some *other*
request has to pull the trigger. That is why it survives review. The diff that introduces it is one
word in a file nobody associates with authorization, and the code that fires it is somewhere else
entirely, written later, by someone else.

## Take it to a review

1. **"Show me where request context is set."** If it is not in one place, it is in several, and
   they will not agree.
2. **"Is it `SET` or `SET LOCAL`?"** One word. Ask for the line.
3. **"Is it inside an explicit transaction?"** `SET LOCAL` outside a transaction block is scoped to
   a statement and will surprise you.
4. **"What does a query with no context return?"** If the answer is "rows", row-level security is
   not the layer they think it is.
5. **"Is the identifier bound, or formatted into the string?"** Context-setting is the one place
   people reach for string building, because `SET` does not accept parameters — which is exactly
   why `set_config(..., true)` is used here instead.

Question 4 is the one that generalises. It is the same question challenge 2.1 asks from the other
direction, and between them they are most of what tenant isolation means in practice.
