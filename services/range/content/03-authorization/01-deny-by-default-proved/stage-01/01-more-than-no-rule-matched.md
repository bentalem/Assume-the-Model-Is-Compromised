# Deny by default means more than "no rule matched"

Everyone agrees with deny by default. Ask what it covers and the agreement gets narrower.

Most people mean: **if no rule says yes, the answer is no.** That is the easy half, it is what the
policy language gives you for free, and it is not where systems fail.

The hard half is everything that is not an answer at all:

| Situation | A system that has thought about it | One that has not |
|---|---|---|
| No rule matched | deny | deny |
| The decision is undefined | deny | crash, or `None` treated as falsey — accidentally right |
| The response is malformed | deny | exception, and then whatever the handler does |
| `allow` came back as the string `"true"` | deny | **allow**, in most languages |
| Two rules conflict | deny | whichever the engine picked |
| The request timed out | deny | retry, then — what? |
| **The engine is unreachable** | **deny** | **this challenge** |

The last row is the one worth an afternoon, because it is the only one that happens **to every
system, eventually, without anybody attacking it.** Deployments, restarts, network partitions, a
full disk, a config reload that failed. The policy engine will be unavailable at some point.

## The trap that externalising creates

Moving the decision out of the application is the right thing to do. The rules become reviewable,
versioned, testable and changeable without a deploy — all of which the lab argues for elsewhere.

It also turns authorization into **a network dependency**, and network dependencies fail.

And at that moment a team faces a choice it usually has not discussed:

- **Fail closed** — refuse everything until the engine is back. The product stops working.
- **Fail open** — allow, on the grounds that this is an outage and not an attack.
- **Fall back to a cached decision** — the compromise, and the worst of the three.

Nobody writes "fail open" on a whiteboard. It arrives as a try/except with a comment about
resilience, added during an incident, by someone trying to keep the service up.

## Why the cache is the worst option

It sounds like the reasonable middle. It is not.

A cached allow is **a standing grant with no revocation**. Revoke a role during an outage and the
cache keeps honouring it. Worse, the cache is warmest for the users who use the system most — so the
people with the broadest access are exactly the ones whose permissions survive longest.

*(Caching a **denial** is fine, and is a different thing entirely. It fails in the safe direction.)*

## What the outage should look like from outside

Two properties, and the second is the one people get wrong:

1. **No data.** Obviously.
2. **Indistinguishable from any other outage.** A `503` that says "the policy engine is down" tells
   an attacker exactly which component to keep pressure on, and tells them the authorization layer
   is the thing currently struggling.

The detail belongs in the logs and the audit trail — where an operator can see it and a caller
cannot. Same shape as the 404 in 7.3 and the opaque validation error in 6.1.

## What you are about to do

Stop the policy engine. Then make a request that works perfectly in normal conditions — alice
reading her own tenant's order, permitted by every rule in the file.

Read what comes back. Then go and find what was written down about it, because the response is
deliberately unhelpful and the trail is not.
