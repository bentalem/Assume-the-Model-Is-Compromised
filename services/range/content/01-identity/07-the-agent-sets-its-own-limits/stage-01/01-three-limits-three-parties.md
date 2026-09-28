# Three limits, three parties

A delegated permission is not one limit. It is three, and the effective permission is what all three allow at once:

```
effective permission  =  what the user may do  ∩  the agent's ceiling  ∩  what this task needs
```

Each term is set by a different party, at a different time:

| Limit | Set by | When | Example |
|---|---|---|---|
| What the user may do | the database — roles | changes over time | alice may read customers and propose refunds |
| The agent's ceiling | an administrator, when the agent is registered | fixed | *a status helper reads orders and nothing else* |
| What the task needs | **trusted code** — the task definition, or the user's explicit consent | every request | *read orders only, for a few minutes* |

In this lab: the first is `app.memberships`, read by the API on every request (challenge 1.3). The second is the profile file the broker loads at start. The third is the operation-to-scope table (`scopes.json`), which the gateway uses to mint exactly one scope per call.

## The third row is the trap

Look at who could set the third limit instead of trusted code: **the agent itself.** It is the obvious design. The agent knows what it is about to do, so let it ask for the scope, and grant what it asks for — as long as the user could do it.

That design holds up as long as the agent is honest. The day it reads an injected instruction, it asks for everything its user can reach, and gets it. The narrowing is still in the diagram; it has become decoration.

> The model proposes; trusted services decide. A scope the agent chooses is a scope the attacker chooses.

## The two limits that must not both be the user

"Agent-requested scopes, auto-approved" collapses two terms into one. The agent's ceiling stops being consulted, so the formula becomes

```
effective permission  =  what the user may do  ∩  whatever the agent asked for
                      =  what the user may do
```

which is passthrough again, reached by a different road: challenge 1.5's failure, now with a token that *looks* narrow and names the agent.

**Next:** the same mistake in systems you may already know.
