# The three choices

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
cannot. Same shape as the 404 you meet in 7.3: **specific inward, opaque outward.**

## What you are about to do

Stop the policy engine. Then make a request that works perfectly in normal conditions — alice
reading her own tenant's order, permitted by every rule in the file.

Read what comes back. Then go and find what was written down about it, because the response is
deliberately unhelpful and the trail is not.
