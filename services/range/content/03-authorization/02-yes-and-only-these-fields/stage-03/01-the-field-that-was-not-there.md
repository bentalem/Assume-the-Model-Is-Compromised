# The field that was not there

## What your result proves

`email`.

```
alice   200   assigned_team, customer_ref, full_name, open_ticket_count
bob     200   assigned_team, customer_ref, email, full_name, open_ticket_count
```

Same endpoint. Same customer. Same code path. **Neither request was refused**, and nothing in the application branched on a role — the field list came back from the policy engine as part of the decision, and trusted code applied it.

Put this beside fiona's request and the shape of the system becomes visible:

| | Status | What happened |
|---|---|---|
| bob | 200 | allowed, full record |
| alice | 200 | **allowed, narrowed** |
| fiona | 404 | refused — wrong role for this action entirely |

A system with a boolean policy has only the first and third. The middle row is the one that makes the sensitive-record case workable, and it is the row most systems cannot express.

Why `404` and not `403` for fiona: a `403` says *the thing exists and you may not have it*. A `404` says nothing at all. For a resource whose existence is itself information, the second is the right answer, and the lab returns it uniformly for "not yours", "not permitted" and "not there". Inside, the audit trail separates them by reason code — challenge 7.3.

## Where the control lives

In two places, deliberately:

1. **The decision, in the rules.** For a restricted customer read by anyone who is not a manager or an auditor, `authz.rego` returns an allow carrying `allowed_fields` — the restricted field set, which has no `email` in it.
2. **The enforcement, in the API.** `Authorization.minimize` in `pipeline.py` keeps only the fields the decision named, between the query and the response. It is an **allowlist**: a field the policy did not name is removed, even one the database returned and the response model would have accepted.

The decision can change under review without a code change. The enforcement cannot be argued with.

## What this check does not cover

Nothing was armed, so there is nothing to restore. Three limits worth knowing:

- **The field is loaded, then removed.** The database returns the whole row to the API process; `minimize` strips it before the response. It never reaches the caller or the model's context — but it did pass through the API's memory.
- **An allow with no field list returns the whole record.** `minimize` only narrows when the decision carries `allowed_fields`. For every other allow, the response model is the only bound on what comes back.
- **A returned obligation nobody applies is a comment.** Here the route calls `minimize`; in another system, the same field list can be returned by the policy and ignored by the code.

## Take it to a review

> **"What can your policy return other than yes and no?"**

Then, depending on the answer:

- **"Nothing"** → their sensitive-data handling is all-or-nothing, and you know that without reading their code. Ask what happens when an agent needs part of a restricted record.
- **"We filter in the response model"** → the data was loaded, was in the process, and for an agent was probably in the model's context. Ask where the filtering happens relative to the query.
- **"The policy returns a field list"** → good. Ask to see the line that applies it.

That last one is the same question as always — *show me the line that acts on the decision* — and it is where obligations most often fall down, because returning them is the interesting part and applying them is boring.

For an agent specifically: an agent that receives a full customer record has that record in its context for the rest of the conversation. Everything it says afterwards is generated from a context containing a contact detail it was not entitled to — and a later instruction, in a ticket, asking it to summarise what it knows is now asking it to summarise a field it should never have had. Filtering the *answer* does not help. The data is already in.

> **An obligation is worth more against an agent than against a UI, because a UI forgets and a context does not.**
