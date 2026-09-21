# Two true sentences

```
the caller was told     404   not_found
the trail recorded      denied   policy_malformed   (no policy version)
```

alice asked for an order she owns, in her own tenant, with the right role. She was told it does not
exist. The order does exist. Nothing about her access changed.

Neither of those lines is a lie. The response is correct — the request could not be satisfied, and
`404` is what this API says when a resource cannot be produced, for the good reason that any other
answer would confirm existence across a tenant boundary. The audit row is correct too, and more
specific: the authorization engine returned something with no decision in it, so the request was
denied.

**The response is true and insufficient. The record is true and sufficient.** An incident is the
difference between those two words.

## The report that would have been written

From the response alone, an account writes itself, and here is what it would say:

> *The customer's order could not be found. Suggest confirming the order number.*

Every part of that is wrong in a way that matters:

- it sends somebody to check an order number that was correct
- it describes a data problem, so it goes to the wrong team
- it produces no incident at all, because "not found" is not an incident
- and the authorization engine stays broken, because nothing in that sentence suggests looking at it

The same request, read from the trail, produces a different first move: *the policy engine is
answering without decisions.* That is an outage, it has an owner, and it is findable in one query.

## Why an agent makes this worse rather than new

None of this is specific to agents. A support engineer reading a `404` would reach the same wrong
conclusion.

What changes is the volume and the confidence. An agent narrates every outcome, immediately, in
fluent prose, to the customer — and its narration is built from exactly the same filtered response,
with no access to the reason behind it. It cannot tell you why it failed, because it was never told.
When it says *"I wasn't able to find that order"*, it is doing its job correctly with the
information it has.

So the failure mode is not a model that lies. It is **a model that faithfully repeats an
insufficient answer, at scale, to the people least able to check it.**

> Never ask what the agent did. Ask what the trail recorded, for that request id.

## What to actually recommend

Not "return better errors to the caller". That would undo a real control, and you will be right to
be argued down.

1. **Make the internal reason reachable by request id.** The caller keeps `404`; the support
   engineer with the request id gets `policy_malformed`. Two audiences, two levels of detail, one
   record.
2. **Put the request id in the response.** This API already sends it. Without it, the trail cannot
   be joined to the complaint, and every investigation starts with a guess.
3. **Alert on the reason, not the status.** `policy_malformed` should page somebody. A `404` never
   will, and this failure produces only `404`s at the edge.
4. **Never accept a narration as an artifact.** If a report says the agent was blocked, ask which
   request id, then go and read the row.

## Take it to a review

1. **"When a request fails, what does the caller see, and what gets written down?"** If they are
   the same string, the trail is not adding anything.
2. **"Can you join a customer complaint to an audit row?"** Only if a request id survives to the
   response.
3. **"Which failures are indistinguishable from outside?"** Every system has some. The list is
   usually shorter than it should be and nobody has written it down.
4. **"What do you alert on — statuses or reasons?"** Statuses miss everything that fails closed
   quietly.
5. **"Show me an incident report written from a transcript."** Then ask what the trail said about
   the same request, and compare.

Question 5 is the one that changes behaviour, because the gap is never theoretical once somebody
has seen it in their own logs.

**Reset before you leave.** The policy engine is currently answering without decisions, and every
measurement in every other challenge is a measurement of that until you do.
