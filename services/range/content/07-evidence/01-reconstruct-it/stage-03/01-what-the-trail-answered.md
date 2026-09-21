# What the trail answered

All six, and the integrity question as well.

```
who asked          the proposing actor id            row 1
who approved       a different actor id              rows 2 and 3
for what           the order on row 1                row 1
under which rules  policy version, and a reason      rows 1-3
what was decided   succeeded / allowed / approved / succeeded
what changed       result_reference on row 4         the provider's own id
```

The chain is linked by `result_reference`: the proposal records the id of the action it created, and
every later step carries that id as its resource. **Four request ids, one action id.**

And the payload hash is identical on propose, approve and execute. That is the sentence that closes
the investigation: the amount that was approved is the amount that was paid, and nothing needed to
be trusted in between — not the queue, not the worker, not the table the payload was sitting in.

## The part that is more interesting than the refund

You ran the column census. Three columns are empty in every row the system has ever written:

| Column | Rows carrying it |
|---|---|
| `trace_id` | 0 |
| `previous_event_hash` | 0 |
| `event_hash` | 0 |

Those last two are a hash chain — each row carrying the hash of the row before it, so that deleting
or editing a row breaks the chain and the break is detectable. It is the standard way of making an
audit trail *tamper-evident* rather than merely *written*.

It is declared in the schema. It is not in the API's `INSERT` statement — not passed as null, not
computed and discarded: **the two column names do not appear in the statement at all.** Both source
panels are above; read the column list in one against the declaration in the other.

Which raises the question this challenge actually turns on, and it is not a rhetorical one.

## So how bad is that?

The obvious conclusion is "the trail can be edited and nothing would show". In this system that is
wrong, and the reason is worth following because it is not the reason people expect.

The API's role cannot touch a written row: `sp_api_role` holds `INSERT` on this table and nothing
else. No runtime role holds `UPDATE` or `DELETE` on it at all. That much is a grant — and since this
is the challenge that says a schema is a promise and a query is evidence, do not take it from me.
One of the observations reads it straight out of the catalogue, one row per command, with the roles
that hold it and the policies that would match. The migration panel below shows where it was
written; the observation shows what is there now.

The owner does hold `UPDATE` and `DELETE` — and still changes nothing. `FORCE ROW LEVEL SECURITY`
applies the table's policies to the owner as well, and this table has **no `UPDATE` policy for
anyone**, so the statement is permitted and matches no rows:

```
UPDATE app.audit_events SET reason = 'edited' WHERE true;
UPDATE 0
```

Not an error. `UPDATE 0`. `DELETE` behaves the same way — and the observation's last column says so
for both, computed from the policies rather than from this paragraph.

Note the shape of that, because it is the whole of challenge 7.3 arriving unannounced: the attempt
was *prevented*, and what it looks like is *nothing happening*. If you were reading a log of that
statement you would see a successful UPDATE.

## One row in that table is not like the others

Read the observation to the bottom. `TRUNCATE` is a table-level command, and row-level security does
not filter it: there are no rows to filter, only one statement that removes all of them. No runtime
role holds it either, so the first half of the finding stands unchanged.

The second half gets sharper. Against the owner, `UPDATE` and `DELETE` are stopped by a policy that
does not exist — and `TRUNCATE` is not stopped by anything at all. An append-only property made of
grants protects the record from the application. It was never going to protect it from the role that
owns the table.

So the accurate finding is two sentences, not one:

> The trail is **append-only**, enforced twice — by grants, and again by row-level security against
> the one role that has the grant. It is **not tamper-evident**: the append-only property is made of
> grants and policies, so it protects the record from the application, and not from anyone who can
> change grants and policies.

That second sentence is what the hash chain was for. A chain survives the administrator; a grant
does not. Whether you need that depends on who you are defending against, and the point is that
**this system currently cannot tell you which of those it chose** — the columns say one thing and
the writer says another.

## Why this is the normal outcome, not a lab joke

Someone designed this table properly. The columns are there because they knew. Then the writer was
implemented against the columns that the first feature needed, and the two that had no immediate
caller were left for later, and later did not arrive. Nothing failed. No test broke — there was
never a test, because the column was never written.

This is what almost all missing controls look like from the inside. Not a decision to skip
something. A correct design, partially implemented, with no check that noticed the gap.

> **A schema is a promise. A query is evidence.** The distance between them is not measured by
> reading code, and it is never visible in a diagram.

## Take it to a review

1. **"Show me one completed sensitive action, end to end, from the log."** Not a description — the
   rows. If nobody can, the trail is not usable in an incident, whatever it contains.
2. **"What links the steps together?"** If the answer is the request id, ask what happens when the
   approver is a different person, because then it cannot be.
3. **"Is the approval bound to the payload?"** Ask for the hash on both rows and compare them
   yourself.
4. **"Which columns in this table are never populated?"** Ask for the counts. Every system has some,
   and what they are tells you which controls were designed and never finished.
5. **"Who can update this table?"** Append-only is a property of grants, not of intentions — and
   ask about `TRUNCATE` in the same breath, because it is the one that row-level security does not
   cover and the one nobody lists.

Question 4 is the one that transfers. It takes one query, it works on any system, and it finds
things nobody is hiding — because nobody knows.
