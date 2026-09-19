# Take it to a real review

You now know something you can check in somebody else's system in about ninety seconds, without
reading their application and without a staging environment.

## Ask for two query outputs

Not access. Not a walkthrough. Two result sets, which any DBA can produce while you wait:

```sql
SELECT c.relname,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity            AS enabled,
       c.relforcerowsecurity       AS forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = '<their schema>' AND c.relkind = 'r';

SELECT rolname, rolsuper, rolbypassrls FROM pg_roles;
```

Then one fact you have to ask a human for: **which role is in the application's connection string.**
Compare it to the `owner` column.

## What a reassuring non-answer sounds like

> *"Yes, we use row-level security — it's in the migrations, you can see the policies."*

Both halves are true and neither is an answer. Policies being present is step 4 of the chain; you
are asking about step 3. Say that plainly and ask again:

> *"I believe you. Which role does the application connect as, and does it own those tables?"*

Two more you will hear:

> *"The app user only has the permissions it needs."*
> Grants and ownership are different things. An owner with `SELECT` only is still an owner, and
> still exempt.

> *"We tested it — tenant A can't see tenant B."*
> Ask which role ran the test. Tests written against a migration or admin connection prove the
> policy's logic and nothing about the path the application takes.

## How to write it up

If you find it, this is a **tenant isolation finding**, not an AI finding. Something like:

```
Row-level security is enabled on <tables> but not forced, and the application connects
as the role that owns them. PostgreSQL exempts a table's owner from its own policies
unless FORCE is set, so the policies are not consulted for application queries. Any
application-layer failure to filter by tenant is therefore unmitigated at the data layer.

Fix: ALTER TABLE ... FORCE ROW LEVEL SECURITY, or move ownership to a role the
application does not use. Verify with the catalogue query above.
```

Two properties of that write-up are worth copying. It **names the mechanism** rather than the
severity, so an engineer can confirm it in one query. And it offers **two fixes**, one of which is a
single statement — because a finding with a one-line remediation gets done this week.

## The habit underneath

This challenge is one instance of something more general, and the general form is the part that
transfers:

> **A control that is configured is not a control that is running.**

Enabled and forced. Written and consulted. Declared and enforced. Every layer in this lab has a pair
like that, and the gap between them is where the afternoon goes. When someone shows you a control,
the useful question is never *"is it there?"* — it is **"what would I observe if it were not?"**

If you cannot answer that, you cannot tell a working control from a decorative one, which is the
position most reviews are conducted from.
