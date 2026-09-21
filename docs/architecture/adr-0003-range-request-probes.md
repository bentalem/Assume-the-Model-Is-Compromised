# ADR-0003 — How the Range makes an API request without being able to reach the API

**Status:** accepted, built
**Supersedes nothing. Constrains:** every remaining challenge in tracks 1, 3, 5 and 8.

## The problem

Twelve of the thirty-one challenges need the learner to make a request *through the API* — present a
token for the wrong audience, read an order after a role was revoked, watch a request fail closed
while the policy engine is down. All of them are blocked on the same thing.

The Range cannot reach the API. That is deliberate and asserted (`V-17`), and it caught the obvious
shortcut once already: the first draft put the Range on the `data` network, the API is also on
`data`, and the check failed on its first run.

So the question is not "how do we let the Range call the API". It is **"what is the smallest thing
that can make a specific API request on the learner's behalf, without giving the Range a general
route to the API"**.

## What was rejected

**Put the Range on `app`.** This is the one-line fix and it is wrong. The whole argument of the
service is that the component with the most authority is bounded like everything else; a boundary
removed the first time it is inconvenient was decoration. It would also delete `V-17`, which is
currently the only thing standing between the Range and every tool the agent can call.

**Let the Range hold a user token.** A service that can mint or hold alice's token can do anything
alice can do, in any combination, forever. That is a service account with extra steps — the
architecture track 1 exists to teach people to recognise.

**Proxy arbitrary requests through a helper.** A helper that takes a method, a path and a body is a
generic tool with a business name. The lab's first rule is that the model never gets one of those;
the Range is held to the same standard, and so is anything built for it.

## The decision

A separate service, `probe`, on the `app` network, exposing a **request registry** — the same shape
as the Range's mutation registry, one level up.

```
probe   app        can reach the API. Holds one credential per lab user.
        control    reachable from the Range, and from nothing else.
```

- Every probe is a **named, parameterless** entry: `alice.read.ord_2001`,
  `alice.read.ord_3001`, `bob.read.cus_4003`, `mallory.read.ord_2001`. The Range sends an id.
- There is **no endpoint that takes a method, a path, a header or a body.** Adding a probe is a code
  change in a reviewed file, exactly like adding a mutation.
- A probe returns only what a challenge needs to show: status code, the `reason` the API recorded,
  and the field names present in the response. **Not the response body** — a learner who needs to
  see data reads it from the database through an observation, where the row cap and the field list
  are already enforced.
- The Range still cannot reach the API. It can ask `probe` to perform one of a fixed list of
  requests, which is a different and much smaller thing.

`V-17` stays exactly as it is.

**Correction to the first draft of this ADR.** It said the probe "must not be reachable from Onyx or
from the API", as though network placement could arrange that. It cannot: the probe sits on `app` so
that it can reach the API, and Docker networks are bidirectional, so anything else on `app` can open
a socket to it.

What actually makes the direction one-way is a **shared secret**, mounted to exactly two services and
compared in constant time. Reachable and usable are different properties, and only the second one is
enforceable here. `V-20` asserts that a request without the secret is refused — which is the real
boundary, rather than the one the network diagram implied.

## Why this is not just moving the problem

It would be, if the probe took a request. It does not. The security property is the same one that
makes `SECURITY DEFINER` acceptable in migration 0010: the privileged thing is reachable **only
through a fixed vocabulary that a human wrote down**, and the vocabulary is the review surface.

The honest cost: adding a challenge in tracks 1, 3, 5 or 8 will usually mean adding a probe, which
is a code change rather than a content change. That breaks the "Phase 2 is content only" rule from
the build brief. It is the right trade — the alternative is a parameter that names a target, and the
whole lab is an argument against those.

## Credentials

`probe` holds one OAuth client credential and obtains user tokens for the five seeded lab users.
Three constraints, and the third is the one that matters:

1. Secrets are mounted per service, as everywhere else. The Range never sees them.
2. Tokens are obtained per probe and not cached beyond their use.
3. **`probe` refuses to start unless `SUPPORTPILOT_ENV` is `local`**, and that refusal is a test —
   the same guard the Range has, for a service holding credentials for five users.

## What this unblocks

1.1, 1.2, 1.3, 1.4, 3.1, 3.4, 5.2, 8.1 — and it is the foundation for the "Range-driven agent
turns" capability in `.dev/ctf/design.md` §5, which is the same idea pointed at Onyx instead of the
API.

## What it does not unblock

Anything needing a model in the loop (4.3, 5.1, 5.3, 7.2) — 5.1 included, because its stated outcome
is an assertion about what the model did. A probe makes an HTTP request; it does not have a
conversation. Those need Onyx, and Onyx is a separate compose project — a later decision,
and a larger one.
