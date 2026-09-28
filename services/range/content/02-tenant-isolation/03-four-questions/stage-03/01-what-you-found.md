# What you found, and how to say it

## What your result proves

The table was `order_items`: enabled, not forced, in a list where every other tenant table was both.

It is a join table, which is exactly why nobody protected it and exactly why it matters. `orders` tells you that a tenant has an order. `order_items` tells you **what they bought, how much of it, and what they paid** — the detail, for every tenant.

You found it the way a reviewer has to: not by reading migrations, but by looking for **one row that disagrees with the rest** in a catalogue a team would honestly describe as correct.

## Where the control lives

Two lines per table, in the migration that creates it — for this one, `0005_orders_detail.sql`:

```sql
ALTER TABLE app.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.order_items FORCE  ROW LEVEL SECURITY;
```

Two lines, nearly identical to the two above them, easy to half-copy. What stops that from shipping in this lab is not the migration — it is the smoke test, which runs the very audit you just ran on every migration and fails the job if any table is not both enabled and forced. That is why this defect could only be armed at run time, never merged.

## What restoring fixes

Restoring sets `FORCE` back, and the catalogue agrees with itself again.

It is worth knowing what did **not** happen while it was armed. `FORCE` only matters to the table's owner, and in this lab the API connects as a role that owns nothing — so every read through the API stayed filtered by the policy the whole time. The exposure was real for anything connecting as the owner, and in the many systems whose application connects as the owner, it would have been every tenant's line items. Two independent layers, and you just watched one of them hold while the other was off.

## Take it to a review

A finding that says "a join table is missing FORCE" gets scheduled. A finding that says "line-item detail for every tenant is readable by the application role" gets fixed this week. Same defect; the second one names the data.

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
- **It says why it was missed.** That is not politeness; it tells the team where to look for the next one, which is the join table added after this one.

The question that generalises:

> An audit is not "does this system have the control". It is "does this system have the control **everywhere**, and how would anyone know".

Any team can show you the control working somewhere. Ask them how they would find the place it is not. If the answer is a person remembering, you have found the next finding already.
