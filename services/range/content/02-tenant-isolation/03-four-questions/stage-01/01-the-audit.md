# Auditing a system you did not build

Challenge 2.1 showed you a broken table and explained why it was broken. That is not the position
you will be in. The real one looks like this:

- You have an hour with somebody else's system.
- You cannot read the application, and you would not have time if you could.
- The team is confident, and their confidence is mostly justified.
- Something is wrong in a place nobody has looked, because if anyone had looked it would be fixed.

What you need is not knowledge of their codebase. It is **a small number of questions whose answers
cannot be argued with**, that you can ask of any system in this class, and that a DBA can answer
while you wait.

## The four questions

1. **Which database role does the application connect as?**
2. **Does that role own the tables?**
3. **Is `FORCE` set, or only `ENABLE`?**
4. **Does that role hold `BYPASSRLS` or `SUPERUSER`?**

Two queries answer three of them. The first is a fact you have to ask a person for, and it is the
one that turns the others into a finding rather than a curiosity.

```sql
-- questions 2 and 3
SELECT c.relname,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity            AS enabled,
       c.relforcerowsecurity       AS forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'app' AND c.relkind = 'r';

-- question 4
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles;
```

## Why both queries, always

A clean first result proves nothing on its own. Every table can be owned by a role the application
never uses, every one of them forced, and the whole thing still filters nothing if the connecting
role holds `BYPASSRLS`.

They are two halves of one question — *is this table filtering for this caller* — and reporting on
one half is how a review produces a confident wrong answer.

## What you are looking for

Not a missing row. **A disagreement between two columns**, in one row, in a list where everything
else agrees.

That is harder than it sounds at sixteen rows and much harder at two hundred, which is why the
second observation in this challenge exists: the same query with the finding already filtered out
of it. Run it first if you like — but notice what it does to your ability to *notice*, and notice
that a client will hand you the unfiltered version.

> A filter that finds the answer for you is a fine tool and a poor exercise. Use the full catalogue
> at least once, so that you know what the odd row feels like.
