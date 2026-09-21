# Denied, or denied visibly

Your policy engine is unreachable. A request arrives. What now?

There are exactly two answers, and one of them is chosen far more often than anyone admits:

| | What it does | What it costs |
|---|---|---|
| **Fail closed** | refuse everything until the engine answers again | an outage becomes a total outage |
| **Fail open** | serve the last decision, or a default allow | **an outage becomes an authorization bypass** |

Fail open is never written down as a decision. It arrives as a fix. The engine flapped in staging,
everything broke, somebody added a cache with a sensible-sounding name, and the pull request said
*"improve resilience when the policy service is unavailable"*. Nobody reviewing it thought they were
reviewing an authorization change, and by every ordinary engineering standard they were not.

> The outage that takes your system down is an incident. The outage that quietly authorizes
> everything is a breach, and you find out about it later, from somebody else.

## This is not the challenge

This lab fails closed, and it will not be made to do otherwise. There is no fallback mode to switch
on — deliberately, and the reasoning is written down in `docs/architecture/adr-0004`: a repository
that teaches people to ask *"what can your runtime turn off about itself?"* cannot also ship a
switch that turns off its own authorization.

So the interesting question here is not *does it fail closed*. Challenge 3.1 already answers that.

It is this:

> **A policy engine can fail in more than one way. Do all of them fail closed — and does anybody
> find out?**

Those are two separate questions, and the second one is where this challenge lives.
