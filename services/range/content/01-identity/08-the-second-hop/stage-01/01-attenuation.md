# Attenuation

Agents hand work to other agents. An orchestrator starts a sub-agent for part of a task; an agent calls a tool that calls another service on the user's behalf. Each of them needs a token, and the obvious way to get one is to exchange the token you were handed for a new one.

That second exchange is where delegation chains go wrong, and the rule that prevents it has a name: **attenuation**. A token passed along a chain may keep authority or lose it. It may never gain it.

```
alice                          everything alice may do
  └─ status-helper             orders:read                  (narrowed by its ceiling)
       └─ refund-assistant     orders:read, or less          (narrowed by what it was handed)
```

The second agent's own ceiling might be much wider than the first's. That does not matter. What it was **handed** is the most it can pass on, because anything more would be authority that nobody in the chain was given.

## What the token records: nested `act`

RFC 8693 records the chain inside the token. Each re-exchange wraps the previous actor:

```json
"act": { "sub": "refund-assistant",
         "act": { "sub": "status-helper" } }
```

Read from the outside in: refund-assistant is acting now, on behalf of status-helper, which was acting for the user in `sub`. The API turns that into a chain in delegation order — `status-helper > refund-assistant` — and records it in the audit row's `agent_id`, beside the human who is still the actor. A chain it cannot read (not an object, a free-text name, deeper than four hops) is refused, not ignored.

## Narrowing in time

Scope is not the only thing that must shrink. A re-exchanged token may not outlive the token it was made from. If it could, re-exchanging just before expiry would extend a task's authority indefinitely, one hop at a time. The broker caps every re-exchanged token at the subject token's remaining lifetime.

## 1.2's lesson, one step along

Challenge 1.2 showed a genuine token refused because it was made for a different audience: a token accepted somewhere it was not meant for is a token whose limits have been ignored. A chain has the same failure one step further along. If the second hop's scope is recomputed from the new holder rather than from the token presented, then the first hop's limit has been ignored — by the component that was supposed to carry it forward.

**Next:** what you are about to run.
