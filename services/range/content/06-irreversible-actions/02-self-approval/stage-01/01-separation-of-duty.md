# Separation of duty

The oldest control in this course, and the one that survives the most.

> **The person who asks for a thing may not be the person who approves it.**

It is older than computers. Two signatures on a cheque, a second pair of eyes on a prescription, the
person who counts the cash not being the person who banks it. It works because it does not depend on
anybody being trustworthy — it depends on **two people having to be wrong at the same time**, which
is a different and much better bet.

## Why it belongs in a course about agents

Because an agent collapses roles that used to be held apart by the fact of being different people.

The agent raises the refund. The agent has the context to justify it. If the agent can also approve
it, then everything downstream of the approval is decided by one component that is steerable by a
customer's ticket text.

And notice what separation of duty does that a permission check does not: an injection that
successfully talks the agent into proposing a fraudulent refund **still has to get past a person who
did not read the ticket.** The control does not care how the request was produced. That property —
indifference to how convincing the request was — is exactly what you want against an attacker whose
whole technique is being convincing.

## The two places it is enforced here, and the screen in front of them

| Where | Refuses because | Removable by |
|---|---|---|
| **Policy** | `input.subject.id == input.resource.requester_id` | editing a policy file |
| **Database trigger** | the row cannot be written at all | a migration |
| Approval portal | it does not refuse on its own: it posts to the API and shows you the answer it gets back | a change to one service |

Two independent implementations of one rule, and a screen that inherits their answer. That looks like
duplication, and it is the opposite.

## Why two is not redundant

Ask the question that separates a defence in depth from a decorative one:

> **Which of these would still hold if someone removed the others this afternoon?**

- Remove the policy rule, and the trigger still refuses — the portal does not, because it has no
  answer of its own to fall back on.
- Replace the portal with a script that posts directly to the API, and policy and the trigger still
  refuse.
- Bypass the API entirely — a migration, a maintenance script, a support engineer with a psql
  session — and **only the trigger is left.**

That last row is the reason the trigger exists. Everything above it protects a path; the trigger
protects the *table*. And the paths that skip the API are exactly the ones nobody models: the
backfill, the incident fix, the data migration, the well-meaning script.

> A control enforced only in the request path protects only the request path. Most damage in real
> incidents does not arrive through the request path.

## And it has to be a trigger, not a constraint

There is a comment in the source below that is worth reading. The rule compares the approver against
the requester — and the requester lives in a **different table**. A `CHECK` constraint can only see
the row it is checking, so it cannot express this.

That is a small detail with a general lesson: **the shape of your invariant decides where it can
live.** A rule about one row can be a constraint. A rule about a relationship needs a trigger, or it
ends up in application code where the next path around the application will miss it.

---

In the console you will attempt the self-approval directly against the database — no API, no portal,
no policy engine. Then run the same approval with a different approver.

**Run both.** The second one is not a formality: without it, "refused" could mean the table refuses
everything, and you would have proved nothing about separation of duty at all.
