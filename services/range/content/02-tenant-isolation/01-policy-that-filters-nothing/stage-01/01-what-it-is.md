# What row-level security is

Most systems keep tenants apart in the application. Every query carries a `WHERE organization_id =
?`, every developer remembers to add it, and every code review checks that they did.

That works until it doesn't, and when it fails there is no second layer. One forgotten clause in one
query is a cross-tenant leak, and nothing else in the stack is in a position to notice.

Row-level security moves the question somewhere else.

> **It is not a check you perform. It is a property of the table.**

Once a row policy is attached, the database rewrites every query against that table to include the
policy's condition — whether the query came from your code, from a migration, from a console, or
from someone who has never heard of your `WHERE` convention. There is no "forgot to add it", because
nobody adds it.

## The three pieces

A working row policy is three separate things, and people usually only picture the middle one.

**1 · The context.** A value that says who is asking. In this lab it is a PostgreSQL run-time
setting, `app.organization_id`, and the API sets it at the start of every request:

```sql
BEGIN;
SELECT set_config('app.organization_id', '1111...', true);   -- true = SET LOCAL
SELECT ... FROM app.orders WHERE order_number = 'ORD-2001';
COMMIT;
```

**2 · The policy.** An expression the database adds to every query on the table:

```sql
CREATE POLICY orders_tenant_read ON app.orders FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());
```

**3 · The switches.** Row security is off until you turn it on, and there are *two* flags, not one.
This is where the challenge lives, and the next tab is about exactly that.

## What "fail closed" means here, concretely

`app.current_org()` reads the setting and returns `NULL` when it is absent:

```sql
CREATE FUNCTION app.current_org() RETURNS uuid
AS $$ SELECT nullif(current_setting('app.organization_id', true), '')::uuid $$;
```

So if the API forgets to set the context, the policy becomes `organization_id = NULL`. In SQL that
evaluates to `NULL` — which is **not** `TRUE` — so no row qualifies.

> Forgetting the tenant returns **nothing**. It never returns **everything**.

That asymmetry is the whole design. A control whose failure mode is silence is worth far more than
one whose failure mode is a log line nobody reads.
