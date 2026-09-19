# Where this failure actually hides

The table that loses `FORCE` is almost never the one the tenant story is about.

Nobody forgets it on `customers`. `customers` is the table everyone pictures when they say "tenant
isolation", it is in the first migration, it is in the design document, and three people have read
that line.

It gets forgotten on the table added eight months later — the join table, the line items, the
attachments, the audit of the audit. Somebody copies the migration above it, adapts the column
names, and misses one of the two `ALTER TABLE` lines. The tests pass, because the tests are about
the entity, not the join. The review passes, because the diff is four lines of obvious DDL.

```sql
ALTER TABLE app.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.customers FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.orders    ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.orders    FORCE  ROW LEVEL SECURITY;
```

Four lines, two of them nearly identical to the other two. Now imagine the fifth and sixth being
added by someone in a hurry.

## So audit the list, not the story

This is the practical consequence, and it is worth carrying:

> **Ask for every table in the schema, not for the tables the team thinks are sensitive.**

A team that is asked "are your tenant tables protected" will answer about the tables they consider
tenant tables. The answer will be honest and it will not cover `order_items`, because nobody thinks
of a line-item table as holding tenant data — even though it holds exactly one thing, which is what
that tenant bought.

## Two more shapes of the same mistake

**The table created outside the migration.** Someone adds a table through a console during an
incident and the DDL never reaches the repository. It has no policy at all. The catalogue shows it;
the migrations do not.

**The table whose policy names the wrong role.** `TO sp_api_role` is correct until the application
grows a second service with its own role, and the policy still names only the first. The catalogue
says enabled and forced; the policy list is where that one shows up. It is a third query, and it is
the right follow-up when the first two come back clean and you still do not believe it:

```sql
SELECT tablename, policyname, roles, cmd
FROM pg_policies WHERE schemaname = 'app';
```

## What none of this catches

Be honest about the limit of the technique. This audit tells you whether the database would filter.
It says nothing about whether the application sets the tenant context in the first place — an
application that never sets `app.organization_id` gets zero rows, which is safe, and one that sets
it from a request parameter gets whatever the caller asked for, which is not.

That is a different question, asked in a different place, and it is track 3.
