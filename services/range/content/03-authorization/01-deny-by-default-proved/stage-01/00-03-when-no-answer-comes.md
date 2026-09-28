# Part 2: when no answer comes

The rules are only half of deny by default. The other half is the code that calls them — `services/api/src/supportpilot_api/policy/client.py` — because that code decides what happens when OPA does not give a proper answer.

Its rule is simple: **anything other than a well-formed decision is a deny.** Two things it deliberately does not have:

- **No cache.** A decision is made for every call. There is no "last known answer" to fall back to.
- **No retry.** A refused call is never repeated with a changed input.

The API waits **250 milliseconds** for OPA, then gives up.

## Every way the answer can fail

| What went wrong | The client's reason | Treated as an outage? | The caller gets |
|---|---|---|---|
| OPA did not answer in time | `policy_unavailable` | yes | `503` |
| OPA could not be reached | `policy_unavailable` | yes | `503` |
| OPA answered with an error status (for example, two rules conflict) | `policy_unavailable` | yes | `503` |
| The body was not JSON | `policy_malformed` | no | `404` |
| The decision the API asked for does not exist | `policy_malformed` | no | `404` |
| `allow` is not a boolean, or the reason or version is missing | `policy_malformed` | no | `404` |

Every row is a **deny**, and every one writes an audit row with that reason and **no policy version** — because no rules decided. That empty column is how you tell, later, that a refusal was not a policy decision at all.

The split between `503` and `404` is one line in `pipeline.py`:

```python
raise unavailable() if decision.unavailable else not_found()
```

An outage becomes `503`, so it is visible to whoever watches for outages. Anything else becomes `404`, the same answer as a policy denial. Challenge 3.4 is about what that second branch hides.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 3.1 | When OPA is stopped, does the API fail closed — and what does it record? |
| 3.2 | What can a decision say besides yes or no, and where is it carried out? |
| 3.3 | For each property, which layer — the rules or the database — actually enforces it? |
| 3.4 | Every way OPA can fail denies. Which of them would nobody notice? |

**Now start challenge 3.1.** The next two tabs explain why "deny by default" means more than "no rule matched".
