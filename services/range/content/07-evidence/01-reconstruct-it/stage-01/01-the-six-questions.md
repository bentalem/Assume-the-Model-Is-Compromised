# Six questions, and one bad assumption

Something went wrong. Money left the company. You have the database and nothing else — no ticket, no
Slack thread, no engineer who remembers.

An investigation is six questions, and they are always the same six:

| | The question | What answers it |
|---|---|---|
| 1 | Who asked for this | an actor identifier |
| 2 | Who allowed it | a second actor, and it had better not be the first |
| 3 | What was it for | a resource |
| 4 | Under which rules | a policy version, and a reason |
| 5 | What was decided | a decision, at each step |
| 6 | What changed outside the system | a reference to the thing that actually happened |

Question 6 is the one people forget, and it is the only one that matters to the customer. A refund
that was authorised and never paid is a different incident from a refund that was paid.

## The bad assumption

Almost everyone starts an investigation by grouping rows by request id, because that is what a
request id is for, and because in a web application it usually works.

> **One action is not one request.** A refund in this system is four requests, made by three
> different actors, over sixteen seconds.

The person who asks cannot be the person who approves — that is the control. The thing that executes
is a separate worker, because the API is not allowed to move money. Each of those is its own request
with its own id, which means **grouping by request id produces four investigations of one row each**,
and each of those rows looks unremarkable on its own.

That is not a flaw in the trail. It is the shape the control forced on it. The separation you are
relying on for safety is the same separation that scatters your evidence, and an investigator who
does not expect that concludes there is nothing to find.

## So what does link them

Something has to, or the system could not have executed the refund either.

Find it in the rows. It is a column whose value in one row is the identifier of another row's
subject — the proposal writes down the identity of the thing it created, and everything that happens
to that thing afterwards names it.

Read the chain forwards and the link is hard to miss. Read any single row and it is invisible.

## Before you start: ask what the trail can answer

There is a habit worth building here, and it costs one query.

A table definition is a statement of intent. It says what someone once meant to record. It does not
say what is in there, and the gap between those two is where investigations die — you build an
argument on a column, and the column is empty in every row that matters.

> **Do not read the schema and believe it. Count the rows.**

One of the observations in the next stage does exactly that, for every column of the audit table.
Run it first. Some of what it tells you is going to be more interesting than the refund.
