# The column that tells you who refused

Every audit row here can carry a `policy_version`. Look at what it means when it is empty.

The API's order of work is fixed, and it is written down in `CLAUDE.md` as a rule rather than left
to whoever edits the file next:

```
validate schema
load trusted resource        <- the database, under row-level security
build policy input
ask OPA                      <- the policy engine
open transaction, set context
parameterised query
apply field obligations
write audit
```

The resource is loaded **before** the policy is asked. That ordering is not an accident — the policy
input has to describe a real resource, and you cannot describe one you were not allowed to load. But
it has a consequence most people do not notice until they go looking:

> If the resource load returns nothing, there is nothing to ask the policy about. The request is
> refused, and **OPA is never consulted**.

A decision that came from the policy engine carries the version of the policy that made it. A
refusal that happened before the engine was reached cannot carry one, because at that moment no
policy had been consulted.

So the column is a witness:

| `policy_version` | What refused |
|---|---|
| present | the policy engine decided, and you can see which version |
| **empty** | **the request never reached the policy engine** |

Challenge 7.3 is built entirely on that distinction. Here it is the tool you need: it lets you tell,
from the trail alone, whether removing a check from the policy could possibly have mattered.

> **When something does not happen, establish whether it was prevented or whether it was never
> asked.** They look identical from outside and they are completely different findings.

---

Arm the first control, run the cross-tenant read, and look at that column before you form an
opinion.
