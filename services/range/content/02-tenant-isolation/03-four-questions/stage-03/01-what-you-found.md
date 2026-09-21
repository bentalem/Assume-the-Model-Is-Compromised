# What you found, and how to say it

The table was `order_items`.

## Why that one is worse than it looks

It is a join table, which is exactly why nobody protected it and exactly why it matters. `orders`
tells you that a tenant has an order. `order_items` tells you **what they bought, how much of it,
and what they paid** — the detail, for every tenant, with no filter.

A finding that says "a join table is missing FORCE" gets scheduled. A finding that says "line-item
detail for every tenant is readable by the application role" gets fixed this week. Same defect;
the second one names the data.

## How to write it

```
app.order_items has row-level security enabled but not forced. PostgreSQL exempts a
table's owner from its own policies unless FORCE is set, so the policy on this table
is not consulted for any query made by the owning role. Every other table carrying
tenant data is configured correctly, which is why this was not noticed.

Impact: line-item detail — quantity, unit price, product — for every tenant, with no
tenant filter applied at the data layer.

Fix: ALTER TABLE app.order_items FORCE ROW LEVEL SECURITY;
Verify: the catalogue query in this finding should return no rows.
```

Three things that make it act on itself rather than sit in a backlog:

- **The verification is a query the reader can run**, not a re-test request to you.
- **The fix is one statement.** A finding with a one-line remediation gets done.
- **It says why it was missed.** That is not politeness; it tells the team where to look for the
  next one, which is the join table added after this one.

## The question that generalises

You were not looking for a bug. You were looking for **one row that disagrees with the rest**, in a
list that a team would describe as correct — and they would be describing it honestly, because
fourteen identical rows and one documented exception is what "we do this" feels like from inside.

> An audit is not "does this system have the control". It is "does this system have the control
> **everywhere**, and how would anyone know".

The second half is the one that finds things. Any team can show you the control working somewhere.
Ask them how they would find the place it is not.

If the answer is a person remembering, you have found the next finding already.
