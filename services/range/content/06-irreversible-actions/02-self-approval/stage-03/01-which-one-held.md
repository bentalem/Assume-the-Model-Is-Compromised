# Which one actually held

**The database trigger.**

```
separation of duty: the requester may not approve their own action
```

Not the policy engine — the attempt never went near it. Not the approval portal — the attempt never
went near that either. The insert went straight at the table, which is the path every backfill,
every maintenance script and every incident fix also takes.

## What the control group told you

The same insert with a different approver was **accepted**, and then removed.

That is the assertion doing the work. Without it, "refused" is ambiguous in a way that matters:

| What you observed | Could also mean |
|---|---|
| the self-approval was refused | approvals cannot be inserted at all |
| | the row was malformed |
| | a grant is missing |
| | the table is read-only to this role |

The second attempt eliminates all of those at once. The row is fine, the grant is fine, the table
takes approvals — **the only thing that changed was who.**

> A refusal proves nothing until you have seen the permitted version succeed. Otherwise you have
> tested that something is broken, not that a rule is enforced.

This is the same discipline as challenge 7.3 from the other direction. There, something failed and
you had to establish whether a control prevented it. Here something was prevented and you had to
establish that the control was *about the thing you think it is about*.

## What to ask a client

Not *"do you enforce separation of duty?"* — everybody says yes, and they are usually telling the
truth about one of the three places.

Ask instead:

1. **Show me where it is enforced.** How many places? Name them.
2. **Which of them still holds if someone writes directly to the database?** A support engineer with
   a psql session during an incident is not a hypothetical; it is Tuesday.
3. **Has anyone tried?** Not "is it implemented" — has a person attempted a self-approval against
   the real table and watched it fail.

Question 3 is the one that finds things, and it is the lab's own rule: a control nobody has watched
fail is a control being trusted, not one that has been tested.

## Writing it up when it is missing

The finding is rarely "there is no separation of duty". It is usually:

```
Separation of duty for <action> is enforced in the application layer only. Any path
that writes to <table> directly — migrations, maintenance scripts, support tooling —
can record an approval by the requester.

Demonstrated: a direct INSERT naming the requester as approver succeeded. The same
row through the API is refused.

Fix: a trigger on <table> comparing the approver to the requester. The comparison
crosses tables, so a CHECK constraint cannot express it.
```

Note what makes that act on itself: it names the paths that bypass the control, it carries a
demonstration rather than an argument, and the fix says why the obvious cheaper option does not
work — so nobody spends a week discovering that on their own.

## The sentence worth keeping

> **A control that lives only in the request path protects only the request path.** Ask which of
> your controls would survive somebody doing the right thing by hand, at three in the morning,
> during an incident.
