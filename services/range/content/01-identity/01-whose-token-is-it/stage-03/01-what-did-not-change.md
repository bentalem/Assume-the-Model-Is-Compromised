# What did not change

`200`.

```
                              unarmed        armed
alice → her own order          200            200
alice → the other tenant       404            404
agent → cedar                  404            200
agent → northwind              404            200
```

**Alice's two rows are identical.** Nothing about her, her token, the API, the policy, or the
database changed. She could not read northwind's order before and she cannot now.

The whole difference is in the bottom two rows, and the only thing that moved is **which credential
was on the call**.

## The blast radius, stated as a number

Under passthrough, a successful injection reaches **what that one user already had**. alice is a
support agent in one tenant; the worst outcome is alice's own access, used badly.

Under a service account it reaches **the union of every user's permissions** — because that is what
the credential holds, because that is what it has to hold.

> Same model. Same prompt. Same tools. Same policy. Same database. **One header value**, and the
> difference between "one agent's access, misused" and "every tenant's data".

That is why this is challenge 1.1 rather than a footnote in the identity track. Nothing else you do
changes the size of the damage by as much.

## And the audit trail says nothing useful

Worth noticing while the environment is armed. Run the audit observation from 7.3 and look at who
those requests were attributed to.

Every one of them is the service account. Not alice. Not the person who typed the message, not the
session it came from, not the customer whose ticket triggered it.

So after an incident, the question *"whose request was this?"* has one answer for every request the
agent ever made — and that answer is the name of the agent.

**Losing enforcement is bad. Losing attribution is worse**, because it removes the ability to find
out what happened afterwards, which is the thing you fall back on when enforcement has already
failed.

## The question to ask, and how to read the answer

> **"Show me one real request the agent sent. What is in the `Authorization` header?"**

| What you see | What you have found |
|---|---|
| The same key every time | architecture A |
| The same key plus a `user_id` field | **architecture B**, and worse than A because it looks safe |
| A short-lived token whose `sub` changes between users | C |

Then the follow-up that settles B:

> **"Where does that `user_id` come from?"**

If the answer traces back to anything the model produced, the per-user access control in their logs
is decoration.

**Reset before you leave** — the agent currently holds a manager's membership in both tenants, and
every measurement you take until it does not is a measurement of that.
