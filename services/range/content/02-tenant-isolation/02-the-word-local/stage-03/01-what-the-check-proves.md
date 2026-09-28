# What the check proves, and how it manages to

## What your result proves

Nothing was armed here, so your result is what the running system does: alice read her order, mallory — another tenant, on the same pool, a moment later — got `404`, and the trail shows two independent decisions. Context from alice's request did not reach mallory's.

`V-12` turns that one observation into a check. It is short enough to hold in your head:

```
for _ in range(6):
    api_get(CEDAR_ORDER, alice)
    api_get(NORTHWIND_ORDER, alice)

count = psql("SELECT count(*) FROM app.orders", "sp_api_role")
if count != "0":
    raise CheckFailed(...)
```

Three decisions in it, and each one is doing work.

**Twelve requests, not one.** A pool hands out whatever connection is free. One request proves nothing — it might get a fresh connection every time. Twelve alternating requests make reuse close to certain, which is what turns "probably fine" into evidence.

**Two order numbers, alternating.** Both calls are made as alice, who belongs to cedar only, so the tenant context is the same each time — what alternates is which order is asked for. One of the two is northwind's and must come back `404` on every pass. A leak that changed what a later request could see would show up as that `404` turning into a row.

**The final question is asked with no context at all.** This is the part worth stealing. It connects as `sp_api_role`, sets nothing, and counts rows. With no `app.organization_id` established, the correct answer is **zero** — every policy fails closed.

> **A test for leaked context has to ask a question that can only be answered by leaked context.** Anything else is measuring the happy path twice.

## Where the control lives

Two places in `db.py`, one behind the other:

1. **`set_config(..., true)` inside `conn.transaction()`.** The `true` is `SET LOCAL`: the value belongs to the transaction and is discarded at `COMMIT`. The identifier is a bound parameter, never text in the statement.
2. **`_reset_connection`**, which the pool runs as every connection comes back: a rollback, then `RESET ALL`. If a session-scoped value were ever set somewhere, it would not survive into the next request.

The first is the control. The second is the belt behind the braces — and the reason is written into its docstring.

## What this check does not cover

Be precise, because the check is good and the claim around it can still be too large.

- It does not prove the pool reused a connection — it makes it overwhelmingly likely, not certain.
- It does not prove *which* mechanism cleaned up, only that nothing survived. `SET LOCAL` and the pool's reset would each pass it on their own.
- **Its final question opens a brand-new connection**, not one from the API's pool. A session-scoped value left behind on a pooled connection is invisible to it. That is the honest limit of this check, and it is why the code above is the control rather than the test.
- It says nothing about the worker, which has its own connections.

That is fine. A check should be named for what it establishes, and this one is: *pooled connections retain no request context between requests.* It claims the outcome rather than the mechanism, which is the right way round.

Even with the word removed, this system would not necessarily leak, and it is worth knowing why before writing the finding. The next request sets its own context before querying, so it overwrites stale values rather than inheriting them. The leak needs a second condition: a request that queries **without** setting context first — a health check, a background read, an endpoint someone added in a hurry. `SET` leaves a loaded gun on the connection, and some *other* request has to pull the trigger. That is why it survives review: the diff that introduces it is one word in a file nobody associates with authorization, and the code that fires it is written later, somewhere else, by someone else.

## Take it to a review

1. **"Show me where request context is set."** If it is not in one place, it is in several, and they will not agree.
2. **"Is it `SET` or `SET LOCAL`?"** One word. Ask for the line.
3. **"Is it inside an explicit transaction?"** `SET LOCAL` outside a transaction block is scoped to a statement and will surprise you.
4. **"What does a query with no context return?"** If the answer is "rows", row-level security is not the layer they think it is.
5. **"Is the identifier bound, or formatted into the string?"** Context-setting is the one place people reach for string building, because `SET` does not accept parameters — which is exactly why `set_config(..., true)` is used here instead.

Question 4 is the one that generalises. It is the same question challenge 2.1 asks from the other direction, and between them they are most of what tenant isolation means in practice.
