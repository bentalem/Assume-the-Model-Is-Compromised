# The five-minute test

## What your result proves

`policy_unavailable`.

```
order.read   denied   policy_unavailable   policy_version: (none)
```

A `503` to the caller, no data, and a row in the trail saying exactly what happened. The request was entirely legitimate — alice, her own tenant, a permitted role, a rule that says yes — and it was refused because **nothing was available to say yes.**

Three things in that one row:

**`denied`, not `error`.** The system is not confused about what it did. It refused, deliberately, and recorded a refusal. A trail full of exceptions during an outage would leave an investigator unable to tell a failure from a decision.

**`policy_unavailable`, a reason of its own.** Not reused from an ordinary refusal. Six months later somebody asking "were any of these requests actually unauthorised?" can separate the outage from the denials in one query.

**No policy version.** Because no policy decided. The same signal as `resource_not_visible` in 7.3: a refusal with no version was refused by something upstream of the rules.

## Where the control lives

Not in the rules — they never ran. In the **client** that calls them, `policy/client.py`: a timeout or a connection failure returns a deny with the reason `policy_unavailable`, marked as a dependency failure. Then one line in `pipeline.py` turns that mark into a `503` rather than a `404`, and the pipeline writes the audit row before refusing.

Two things are missing from that client on purpose: there is **no cache** of earlier decisions to fall back on, and **no retry**. The rules file contributes the other half of deny by default — a `default decision` that denies when no rule matches — but during an outage, the client is the whole control.

## What restoring fixes

Restoring starts OPA again and waits until it is running, and the next request is allowed as before. Because nothing was cached, there is nothing stale to clear: no decision made before the outage outlives it, and nothing was allowed during it.

What the outage leaves behind is useful rather than harmful: every request it refused is in the trail with `policy_unavailable` and no version. You can count exactly which requests the outage cost, and prove none of them was served.

## Take it to a review

It costs one command, needs no code access, and the answer is not guessable:

> **"Stop the policy engine and repeat a request that normally works. What happens?"**

| What happens | What you have found |
|---|---|
| `503`, no data, a recorded denial | fails closed. Ask to see the test that proves it stays that way |
| `200` with data | **fail open.** The finding writes itself |
| `200` with data, only for some users | **a cache.** A standing grant with no revocation |
| Nobody will run it | usually the most informative answer available |

That last row is not a joke. A team that will not stop the policy engine in a staging environment has generally worked out what would happen and would rather not say so on the record.

Fail-open and cached-allow look identical for the first few seconds of an outage, and then diverge: a cache serves the users who were recently active and refuses everyone else. So if the answer is "it kept working", the follow-up is:

> **"For everyone, or only for people who had used it recently?"**

The second is a cache, and a cache of *allow* decisions is a standing grant. Ask what revokes it.

And why this matters more with an agent: an agent makes many more authorization decisions than a person does, in bursts, often unattended. An outage that degrades to fail-open for ninety seconds is ninety seconds during which a steerable component had unbounded authority — and nothing in the transcript will look unusual, because from the agent's point of view everything worked.

> **Externalising the decision is right. Fail-closed is what makes it safe.** One without the other is a well-organised authorization layer with an off switch.

**Reset before you leave** — until the policy engine is back, every measurement you take is a measurement of a broken system.
