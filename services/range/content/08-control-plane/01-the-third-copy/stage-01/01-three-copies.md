# Three copies

It feels like a silly question. The tools are in the code — you can read them.

Then you go and count, and in this system there are three copies of that list, in three different
places, kept in step by three different mechanisms. One of those mechanisms is a person.

| | Copy | What it is | Kept in step by |
|---|---|---|---|
| 1 | **the code** | the modules that register each operation | it *is* the source of truth |
| 2 | **the exported document** | `openapi/supportpilot-actions.json` | a check on every commit |
| 3 | **the agent's registered actions** | whatever the agent platform holds | ? |

Two of the observations in the next stage show you copies 1 and 2. There is no observation for copy
3, and that is not an oversight in this challenge — it is the finding, arriving early.

## The check that exists, and what it says

Every commit runs a check that regenerates the document from the code and compares the two. When it
passes it prints:

```
OK: action document matches the code. Operations: add_internal_note, get_action_status, ...
```

That is a real control and it closes a real gap. Before it, a tool could change while the document
kept describing the old one, and nobody would notice until an agent called something that no longer
existed.

Read the sentence carefully though. **"Matches the code."** It compares copy 2 against copy 1. It is
a *comparison*, not a deployment — it does not push anything anywhere, and it makes no claim about
copy 3, because it has no way to see it.
