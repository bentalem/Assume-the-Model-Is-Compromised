# The five-minute test

`policy_unavailable`.

```
order.read   denied   policy_unavailable   policy_version: (none)
```

A `503` to the caller, no data, and a row in the trail saying exactly what happened. The request was
entirely legitimate — alice, her own tenant, a permitted role, a rule that says yes — and it was
refused because **nothing was available to say yes.**

## Three things in that one row

**`denied`, not `error`.** The system is not confused about what it did. It refused, deliberately,
and recorded a refusal. A trail full of exceptions during an outage would leave an investigator
unable to tell a failure from a decision.

**`policy_unavailable`, a reason of its own.** Not reused from an ordinary refusal. Six months later
somebody asking "were any of these requests actually unauthorised?" can separate the outage from the
denials in one query.

**No policy version.** Because no policy decided. The same signal as `resource_not_visible` in 7.3:
a refusal with no version was refused by something upstream of the rules.

## Why this test is worth doing on every engagement

It costs one command, needs no code access, and the answer is not guessable:

> **"Stop the policy engine and repeat a request that normally works. What happens?"**

The possible outcomes and what each means:

| What happens | What you have found |
|---|---|
| `503`, no data, a recorded denial | fails closed. Ask to see the test that proves it stays that way |
| `200` with data | **fail open.** The finding writes itself |
| `200` with data, only for some users | **a cache.** A standing grant with no revocation |
| Nobody will run it | usually the most informative answer available |

That last row is not a joke. A team that will not stop the policy engine in a staging environment
has generally worked out what would happen and would rather not say so on the record.

## The one that hides

Fail-open and cached-allow look identical for the first few seconds of an outage, and then diverge:
a cache serves the users who were recently active and refuses everyone else.

So if the answer is "it kept working", the follow-up is:

> **"For everyone, or only for people who had used it recently?"**

The second is a cache, and a cache of *allow* decisions is a standing grant. Ask what revokes it.

## And why this matters more with an agent

An agent makes many more authorization decisions than a person does, in bursts, often unattended. An
outage that degrades to fail-open for ninety seconds is ninety seconds during which a steerable
component had unbounded authority — and nothing in the transcript will look unusual, because from
the agent's point of view everything worked.

> **Externalising the decision is right. Fail-closed is what makes it safe.** One without the other
> is a well-organised authorization layer with an off switch.

**Reset before you leave** — the policy engine is currently stopped, and every measurement you take
until it is back is a measurement of a broken system. Reset waits for it to be running again before
it reports success.
