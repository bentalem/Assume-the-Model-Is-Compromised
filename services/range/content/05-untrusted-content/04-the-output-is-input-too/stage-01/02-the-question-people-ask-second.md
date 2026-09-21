# The question asked second

## The question people ask second

Open the source panels and the escaping answer is there to read. That is the second question.

The first one is:

> **Which of these values could an attacker have chosen, and how wide is the widest string they
> could put in one?**

Ask it in that order and you will sometimes find that the answer is "none of them", at which point
the escaping is a second layer rather than the only one. Ask it in the other order and you will
report on quoting while an unbounded field goes unmentioned.

So before you read a single `html.escape` call, work out the shape of what reaches the page:

| Value on the screen | Where it comes from |
|---|---|
| Action, Requested by, Organization, Resource | the action request row, server-derived |
| Amount, Currency | the frozen payload |
| Reason | the frozen payload |
| Risk level, State, Expires | constants and server state |
| Exact payload to execute | the canonical form of the frozen payload |
| sha256 | a hex digest |

Then go to `propose_refund` and find out what a caller is allowed to put into each of those.

## Why this matters more than it looks

The approval portal exists to be the independent check on an irreversible action. Track 6 is built
on that: the API never performs the effect, an approver approves the exact payload hash, and the
worker executes once.

Every one of those controls is structural and none of them helps if the *screen lies*. An approver
who is shown one amount and signs a hash for another has performed the review perfectly and approved
the wrong thing. That is challenge 6.1, and it is the reason the portal shows the canonical payload
and the hash side by side rather than a tidied summary.

A rendering bug in this service is therefore not an XSS finding with a severity of "medium because
it is internal". It is a hole in the one control that exists to stop a refund nobody agreed to.

## What to have ready before Stage 03

- The number of distinct values interpolated into the review page, and what each passes through.
- What `html.escape` does with a single quote when you do not pass `quote`.
- The list of fields `propose_refund` accepts, the list of keys it freezes, and the difference
  between those two lists.
