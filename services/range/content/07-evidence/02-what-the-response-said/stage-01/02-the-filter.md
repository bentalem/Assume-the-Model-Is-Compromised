# The filter

## The filter

A response has a small vocabulary. The whole list this API can say is in the second source panel,
and it is short: not found, conflict, business rule, rate limited, unavailable, and a few more.

The audit trail has a different vocabulary, and it is much larger: the reason a control gave, the
policy version that produced it, the actor, the resource, the decision.

Those two vocabularies do not map onto each other one-to-one, and where they do not, the response
has to pick something. That choice is deliberate, defensible, and the reason this challenge exists.

Two of the choices in this system:

| Situation | What the caller is told | Why |
|---|---|---|
| The order is in another tenant | `404 not_found` | so a refusal never confirms a resource exists elsewhere |
| A dependency is down | `503 unavailable` | so an outage is visible as an outage |

The first one is a real control. Answering `403 forbidden` would confirm the order exists, which is
a tenant-isolation leak delivered by a status code. `404` is the right answer.

But notice what it costs: **two very different situations now produce the same word.** "It is not
here" and "it is here and you may not have it" are indistinguishable from outside, on purpose.

## What you are going to do

Arm the control on this page. It leaves the policy engine running and healthy, answering requests,
with no decision in its answer — challenge 3.4 is about that failure itself; here it is just a
convenient way to produce one.

Then have alice ask for `ORD-2001`. She owns it. It is in her tenant, she has the role, and nothing
about her has changed.

Read what she is told. Then read what was written down.

Then write the sentence that an incident report would contain if it were built from the first, and
decide whether that sentence is true.
