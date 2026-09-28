# What the checks verify, and where they run

A check on the control plane is only as good as two things: **what it compares**, and **when it runs**. This tab lists both for every control-plane check in the lab, so that in each challenge you can read a green line for its exact scope.

## The export audit

`scripts/export_openapi.py` builds the action document from the running API code. Before it writes anything, it audits the result. The document is refused — nothing is written — if any of these is true:

| Rule | Why it exists |
|---|---|
| an operation is **not in `APPROVED_OPERATIONS`** | a new tool is a control-plane change, not a side effect of writing a route |
| an approved operation is **missing** | the approved set and the real set must agree in both directions |
| an operation has **no summary** | the model needs text to choose by — the check tests that it exists, not what it says |
| a parameter is named `user_id`, `organization_id`, `role`, `approved`, `state`… | identity and approval are derived by the server (rule 1) |
| a header is exposed to the model | authentication headers are supplied by the runtime, never chosen by the model |
| a string parameter has no pattern, length or enum | every input the model supplies is bounded |
| a query parameter is an array | clients serialise arrays differently; one shape, one parser |
| a response has no schema, a schema allows extra properties, or an array has no `maxItems` | bounded output (rule 11) |

`APPROVED_OPERATIONS` is a literal set of seven names in the script itself. Adding a tool therefore needs **two** changes in one pull request: the route, and the approved list. That is the whole mechanism by which a new tool becomes visible to a reviewer.

## `--check`: the same audit, plus a comparison

With `--check`, the script writes nothing. It regenerates the document in memory and compares it with the committed file, byte for byte. When both agree, it prints:

```
OK: action document matches the code. Operations: add_internal_note, get_action_status, ...
```

That sentence is precise: **the committed document matches the code.** It says nothing about any other copy.

## Where the check actually runs

This matters more than what it checks, and it is easy to get wrong:

| Where | When |
|---|---|
| by hand: `python scripts/export_openapi.py --check` | when somebody remembers |
| `scripts/abuse_suite.py`, case `TS7-12` | when somebody runs the abuse suite |
| a local pre-commit hook | only on a machine where one was installed — `.githooks/` is not part of the published repository |

There is no CI pipeline in this repository. So "checked on every commit" is true on a machine with the hook installed, and not otherwise — and a reader of a green line cannot tell which kind of machine produced it.

## The other control-plane checks

| Check | What it measures |
|---|---|
| V-19, V-21 | the action document never names the Range or the probe service |
| V-30 | the memory service's separate document holds exactly its four model operations (track 9) |
| V-02 | from inside the approval portal, on `edge`, PostgreSQL and OPA do not answer |
| V-17 | from inside the Range, the API and OPA do not answer |

V-02 and V-17 are a different kind of check from the rest. They do not read a file; they **open a socket** in a running container and report what answered. Challenge 8.2 is about why that difference matters.

## What nothing checks

Say these out loud before starting the track, because each challenge is about one of them:

- **the copy of the tool list the agent actually holds** — 8.1
- **what a URL-taking tool would reach**, because there is no such tool to check, only a network to read — 8.2
- **a tool list that arrives at runtime**, because this lab has none, and every check above runs before deploy — 8.3
- **whether anyone agreed to a tool's description** — 8.4

## Where the track goes

| Challenge | The artifact | The question |
|---|---|---|
| 8.1 | three copies of the tool list | which copy does nothing check? |
| 8.2 | the network map | what would a URL-taking tool reach, and which control decides that? |
| 8.3 | a tool list fixed at build time | what changes if the list arrives over the network? |
| 8.4 | the text describing each tool | which of the lab's controls cover a change to it? |

Every challenge in this track is read-only. Nothing is armed, because the findings are absences — and arming something would put a different question on the page.
