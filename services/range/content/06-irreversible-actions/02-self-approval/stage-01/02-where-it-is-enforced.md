# Where it is enforced

## The three places it is enforced here, and the screen that is not one of them

| Where | Refuses because | Removable by |
|---|---|---|
| **Policy** | `input.subject.id == input.resource.requester_id` | editing a policy file |
| **Row policy** | the insert requires `approver_id = app.current_user_id()`, the `finance_approver` role, a `PENDING_APPROVAL` state and an unexpired window — all at once | a migration |
| **Database trigger** | the row cannot be written at all when requester and approver match | a migration |
| Approval portal | *nothing* — it posts to the API and renders the answer it gets back | a change to one service |

Three independent implementations of one rule, and a screen that inherits their answer. That looks
like duplication, and it is the opposite. Note which one is not on the list: the thing the approver
is actually looking at holds no rule of its own, which is exactly right — a screen that could
decide would be a screen an attacker could reach.

## Why three is not redundant

Ask the question that separates a defence in depth from a decorative one:

> **Which of these would still hold if someone removed the others this afternoon?**

- Remove the policy rule, and the row policy and the trigger still refuse — the portal does not,
  because it has no answer of its own to fall back on.
- Replace the portal with a script that posts directly to the API, and all three still refuse.
- Grant the API's role more than it should have, and the row policy stops applying — the trigger
  does not, because a trigger is not a permission.
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
