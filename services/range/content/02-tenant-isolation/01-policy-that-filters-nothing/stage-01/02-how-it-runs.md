# How it actually runs

Two flags, and they are not the same flag.

```sql
ALTER TABLE app.orders ENABLE ROW LEVEL SECURITY;   -- consult the policies
ALTER TABLE app.orders FORCE  ROW LEVEL SECURITY;   -- consult them for the owner too
```

`ENABLE` turns the feature on. `FORCE` decides whether the table's **owner** is subject to it.

## Why an owner exemption exists at all

It is not an oversight. Without it, the person who owns a table could lock themselves out of their
own data and could not run a migration, a backfill, or a repair. PostgreSQL's default is that an
owner is trusted with their own table, and `FORCE` is how you say *"not even me"*.

That default is correct for a database administrator. It is wrong for an application — and whether
your application is an administrator depends on a detail that lives nowhere near the policy.

## The order the database actually works in

When a query arrives against a table with row security enabled, PostgreSQL asks, in this order:

1. **Is row security enabled on this relation?** No → return everything the grants allow.
2. **Does this role bypass it?** `SUPERUSER`, or the `BYPASSRLS` attribute → return everything.
3. **Is this role the table's owner, and is `FORCE` off?** → return everything.
4. Otherwise → rewrite the query with every applicable policy's `USING` expression and run that.

Read step 3 again. It does not look at the policy. It does not look at the query. **It looks at who
owns the table**, and the policy — however correct — is never consulted.

## Where the answer to step 3 lives

Not in the policy. Not in the query. Not in any file a reviewer is reading when they review the data
layer.

```
  connection user   sp_api_role        ← this
  table owner       sp_migrator_role   ← compared against this
```

In this lab those two are deliberately different: `sp_migrator_role` owns every table, and
`sp_api_role` — the role in the connection string — owns nothing. Build rule 5 exists for exactly
this reason, and it is checked on every migration run rather than remembered.

But it is very common for them to be the same, and not through carelessness. Watch how a real system
arrives there:

1. A developer creates the database and a user, `app_user`.
2. They run the migrations — as `app_user`, because that is the user they have.
3. The application connects — as `app_user`, because that is what is in the config.
4. A year later, somebody says "we need tenant isolation". They add `ENABLE ROW LEVEL SECURITY` and
   a policy. The policy is perfect.
5. **It filters nothing**, because of a decision made in step 2 by someone who was not thinking
   about step 4.

Nobody made a mistake in step 4. **This is not a bug in the code; it is a bug in the history of the
system** — and that is why reading the code will not find it.
