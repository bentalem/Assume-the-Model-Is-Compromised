# Which one actually held

## What your result proves

**The database trigger.**

```
separation of duty: the requester may not approve their own action
```

Not the policy engine — the attempt never went near it. Not the approval portal — the attempt never went near that either. The insert went straight at the table, which is the path every backfill, every maintenance script and every incident fix also takes.

The same insert with a different approver was **accepted**, and then removed. That control group is what makes the result mean something:

| What you observed | Could also have meant |
|---|---|
| the self-approval was refused | approvals cannot be inserted at all |
| | the row was malformed |
| | a grant is missing |
| | the table is read-only to this role |

The second attempt eliminates all of those at once. The row is fine, the grant is fine, the table takes approvals — **the only thing that changed was who.**

> A refusal proves nothing until you have seen the permitted version succeed.

## Where the control lives

In `app.enforce_separation_of_duty()`, a trigger on `app.approval_decisions` (migration `0008`). It looks up the request's `requester_id` and refuses the row when the approver matches.

It has to be a trigger rather than a `CHECK` constraint, and the comment in the source says why: the rule compares the approver against the requester, and the requester lives in a **different table**. A constraint can only see the row it is checking. The shape of an invariant decides where it can live — a rule about one row can be a constraint; a rule about a relationship needs a trigger, or it ends up in application code where the next path around the application will miss it.

The trigger is one of four places the rule is enforced. The policy refuses `refund.approve` when the subject is the requester; the approval row policy accepts a decision only under the approver's own id and a `finance_approver` role; the worker checks the approver against the requester again before executing. Ask which would still hold if someone removed the others: bypass the API entirely — a migration, a script, an engineer with a psql session — and **only the trigger and the worker are left**, and only the trigger stops the row being written at all.

## What this check does not cover

Both attempts rolled themselves back, so there is nothing to restore.

The trigger compares **identities**, not people. It stops one person approving their own request. It does not stop two people who agree — a requester and a colluding approver pass every check in this lab, correctly. Separation of duty makes fraud need two participants; it does not make it impossible. That is its whole promise, and it is worth stating when a team thinks it promises more.

## Take it to a review

Not *"do you enforce separation of duty?"* — everybody says yes, and they are usually telling the truth about one of the places. Ask instead:

1. **Show me where it is enforced.** How many places? Name them.
2. **Which of them still holds if someone writes directly to the database?** A support engineer with a psql session during an incident is not a hypothetical; it is Tuesday.
3. **Has anyone tried?** Not "is it implemented" — has a person attempted a self-approval against the real table and watched it fail.

When it is missing, the finding is rarely "there is no separation of duty". It is usually:

```
Separation of duty for <action> is enforced in the application layer only. Any path
that writes to <table> directly — migrations, maintenance scripts, support tooling —
can record an approval by the requester.

Demonstrated: a direct INSERT naming the requester as approver succeeded. The same
row through the API is refused.

Fix: a trigger on <table> comparing the approver to the requester. The comparison
crosses tables, so a CHECK constraint cannot express it.
```

It names the paths that bypass the control, it carries a demonstration rather than an argument, and the fix says why the obvious cheaper option does not work.

> **A control that lives only in the request path protects only the request path.** Ask which of your controls would survive somebody doing the right thing by hand, at three in the morning, during an incident.
