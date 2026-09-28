# What did not change

## What your result proves

```
                              unarmed        armed
alice → her own order          200            200
alice → the other tenant       404            404
agent → cedar                  404            200
agent → northwind              404            200
```

**Alice's two rows are identical.** Nothing about her, her token, the API, the policy or the database changed. She could not read northwind's order before and she cannot now.

The whole difference is in the bottom two rows, and the only thing that moved is **which credential was on the call**.

### The blast radius, stated as a number

Under passthrough, a successful injection reaches **what that one user already had**. alice is a support agent in one tenant; the worst outcome is alice's own access, used badly.

Under a service account it reaches **the union of every user's permissions** — because that is what the credential holds, because that is what it has to hold.

> Same model. Same prompt. Same tools. Same policy. Same database. **One header value**, and the difference between "one agent's access, misused" and "every tenant's data".

That is why this is challenge 1.1 rather than a footnote. Nothing else you do changes the size of the damage by as much.

## Where the control lives

There is no bug in the API here, and that is the point. The API did exactly for the service account what it does for alice:

1. `dependencies.py` takes whatever is in the `Authorization` header and verifies it. The token was genuine.
2. `load_subject` asked the database who `agent-service-id` is. Unarmed, the answer was "a user with no memberships". Armed, it was "a `support_manager` in cedar **and** in northwind".
3. The order lookup ran once per tenant the subject belongs to. Armed, that includes northwind, so ORD-3001 was found — and the policy saw a manager in the order's tenant.

Arming inserted two rows into `app.memberships` (`range.arm_service_account`, migration 0026). The control that decides the outcome is not in the API at all. It is the choice of **which token the runtime puts on the call** — in this lab, Onyx's "Pass through user's OAuth token" setting from LAB.md B10.

## What restoring fixes

Reset deletes the service account's memberships. From the next request, it reaches nothing again.

What reset cannot fix is the audit trail written while it was armed. Run the audit observation from 7.3 and look at who those requests were attributed to: every one of them is **the service account**. Not alice, not the person who typed the message, not the customer whose ticket triggered it.

So after an incident, *"whose request was this?"* has one answer for every request the agent ever made — and that answer is the name of the agent. **Losing enforcement is bad. Losing attribution is worse**, because it removes the ability to find out what happened afterwards, which is what you fall back on when enforcement has already failed.

## Take it to a review

> **"Show me one real request the agent sent. What is in the `Authorization` header?"**

| What you see | What you have found |
|---|---|
| The same key every time | architecture A |
| The same key plus a `user_id` field | **architecture B**, and worse than A because it looks safe |
| A short-lived token whose `sub` changes between users | C |
| A short-lived token naming the user in `sub`, the agent in `act`, and a narrow `scope` | D — and then ask what reads the scope (1.5 – 1.8) |

Then the follow-up that settles B:

> **"Where does that `user_id` come from?"**

If the answer traces back to anything the model produced, the per-user access control in their logs is decoration.

**Reset before you leave** — until you do, the agent holds a manager's membership in both tenants, and every measurement you take is a measurement of that.
