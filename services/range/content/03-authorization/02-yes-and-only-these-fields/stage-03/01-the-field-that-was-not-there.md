# The field that was not there

`email`.

```
alice   200   assigned_team, customer_ref, full_name, open_ticket_count
bob     200   assigned_team, customer_ref, email, full_name, open_ticket_count
```

Same endpoint. Same customer. Same code path. **Neither request was refused**, and nothing in the
application branched on a role — the field list came back from the policy engine as part of the
decision, and trusted code applied it.

## Three outcomes, not two

Put this beside fiona's request and the shape of the system becomes visible:

| | Status | What happened |
|---|---|---|
| bob | 200 | allowed, full record |
| alice | 200 | **allowed, narrowed** |
| fiona | 404 | refused — wrong role for this action entirely |

A system with a boolean policy has only the first and third. The middle row is the one that makes
the sensitive-record case workable, and it is the row most systems cannot express.

## Why `404` and not `403` for fiona

Worth noticing while it is in front of you. A `403` says *the thing exists and you may not have it*.
A `404` says nothing at all.

For a resource whose existence is itself information — an order, a customer, a ticket — the second
is the right answer, and the lab returns it uniformly for "not yours", "not permitted" and "not
there". From outside, those are indistinguishable. Inside, the audit trail separates them by reason
code, which is challenge 7.3.

## What to ask a client

> **"What can your policy return other than yes and no?"**

Then, depending on the answer:

- **"Nothing"** → their sensitive-data handling is all-or-nothing, and you know that without reading
  their code. Ask what happens when an agent needs part of a restricted record.
- **"We filter in the response model"** → the data was loaded, was in the process, and for an agent
  was probably in the model's context. Ask where the filtering happens relative to the query.
- **"The policy returns a field list"** → good. Ask to see the line that applies it. A returned
  obligation nobody enforces is a comment.

That last one is the same question as always — *show me the line that acts on the decision* — and it
is where obligations most often fall down, because returning them is the interesting part and
applying them is boring.

## For an agent specifically

The reason this matters more with a model in front of it:

An agent that receives a full customer record has that record in its context for the rest of the
conversation. Everything it says afterwards is generated from a context containing a contact detail
it was not entitled to — and a later instruction, in a ticket, in a document, asking it to summarise
what it knows is now asking it to summarise a field it should never have had.

Filtering the *answer* does not help. The data is already in.

> **An obligation is worth more against an agent than against a UI, because a UI forgets and a
> context does not.**
