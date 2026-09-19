# The failure geometry

Everything that has to be true, and what happens when each one is not. This is the tab worth
keeping.

## The truth table

A cedar request is in context. The question is whether a northwind row comes back.

| Enabled | Forced | Connected as | Policy consulted | Northwind rows |
|---|---|---|---|---|
| no | — | anything | no | **all of them** |
| yes | no | **the owner** | **no** | **all of them** |
| yes | no | a non-owner | yes | none |
| yes | yes | the owner | yes | none |
| yes | yes | a non-owner | yes | none |
| yes | yes | a role with `BYPASSRLS` | **no** | **all of them** |
| yes | yes | a superuser | **no** | **all of them** |

Four ways to be exempt. Only one of them is visible in the table's definition.

## Which of these a review catches

| Failure | How it looks in a schema dump | How it looks in a code review |
|---|---|---|
| Row security never enabled | **obvious** — no `ENABLE` line | invisible |
| `BYPASSRLS` on the app role | invisible | invisible |
| Superuser in the connection string | invisible | invisible |
| **Owner connects, `FORCE` absent** | **looks correct** | **looks correct** |

The last row is the one this challenge is about, and it is the worst of the four — not because it is
the most severe, but because **everything a reviewer looks at says it is fine**:

- The policy is correct. Read it; it is right.
- The query is correct. Parameterised, context set, everything in order.
- `\d app.orders` **shows the policy**. It is really there.
- The tests pass, if they were written using a different role.

The only wrong thing is a username in a connection string, in a config file, in a different
repository, read by nobody during the review of the data layer.

## The four questions

Never ask a team *"do you use row-level security?"* — the answer is always yes, and it is always
true, and it tells you nothing.

Ask these instead. One catalogue query answers the first three:

1. **Which database role does the application connect as?**
2. **Does that role own the tables?**
3. **Is `FORCE` set, or only `ENABLE`?**
4. **Does that role hold `BYPASSRLS` or `SUPERUSER`?**

```sql
SELECT c.relname,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity            AS enabled,
       c.relforcerowsecurity       AS forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'app' AND c.relkind = 'r';

SELECT rolname, rolsuper, rolbypassrls FROM pg_roles;
```

You do not need access to the application to run either of them. That is what makes them the first
two things to ask for.
