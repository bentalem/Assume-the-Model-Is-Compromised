# One word

Row-level security in this system works by asking the database a question it can only answer if it
knows who is asking:

```sql
SET LOCAL app.user_id         = '...'
SET LOCAL app.organization_id = '...'
```

Every policy reads those through `app.current_org()` and `app.current_user_id()`. Get them right and
a tenant sees its own rows. Get them wrong and it sees somebody else's.

Now delete one word:

```sql
SET app.user_id         = '...'
SET app.organization_id = '...'
```

Both versions work. Both pass every test you would write for a single request. Both set the values,
both return the right rows, and for the whole length of one transaction **they are indistinguishable**.

## Where they stop being the same

`SET LOCAL` is scoped to the transaction. `SET` is scoped to the **session** — which means, on a
pooled connection, to the connection.

That distinction is invisible until the transaction ends. Here is the sequence that matters, and it
is worth reading slowly because it is the entire challenge:

| | With `SET LOCAL` | With `SET` |
|---|---|---|
| Request 1 arrives, takes a connection from the pool | — | — |
| sets context, runs its query | context set | context set |
| transaction ends, connection returns to the pool | **context gone** | **context still set** |
| Request 2 arrives, gets the same connection | — | — |
| ...and forgets to set context | no context: policies fail closed | **request 1's context** |

That last cell is the bug. Request 2 does not get an error and does not get nothing. It gets
somebody else's tenant, with every policy working perfectly, because the policies were told a lie
about who was asking.

## What PostgreSQL actually does

Not an argument — the behaviour, from the database itself. A procedure sets both kinds of value,
commits (the moment request 1 ends), and then looks again:

```
PERFORM set_config('app.demo_session', 'alice', false);   -- SET
PERFORM set_config('app.demo_local',   'alice', true);    -- SET LOCAL
COMMIT;                                                    -- request 1 ends here
```

```
request 2 sees ->  SET: alice    SET LOCAL: (gone)
```

Two settings, made in the same breath, on the same connection. After the commit one of them is
still there waiting for whoever gets that connection next.

## Why this is not an armable control

Every other challenge in this track lets you break something and watch. This one does not, and the
reason is worth stating rather than hiding.

`SET` instead of `SET LOCAL` is not a control at its wrong setting, the way row-level security being
disabled is. It is **a code path that leaks request context between users** — and making it
switchable would mean the API permanently contains that path, one environment variable from being
live, in the repository whose whole argument is that a runtime should not be able to turn its own
authorization off. `docs/architecture/adr-0004` records that decision.

So this challenge is a reading exercise, and the thing you are reading is one word in one statement
that everything else in track 2 depends on.

## What to do

Read the first source panel. Find the word, and note two things about the code around it: the
context is set with a bound parameter rather than string-built SQL, and it is inside an explicit
transaction rather than on a bare connection.

Then read the second panel, which is the check that would catch the word going missing. Work out
what it actually proves — and, in particular, why it asks its final question with no context set at
all.
