# Start here: the control plane

Read these two architecture tabs before you start challenge 1 of track 8. They describe the part of the system that none of the earlier tracks tested, because it is not made of requests.

Tracks 1–7 tested the **data plane**: a request arrives, and the system decides whether to allow it. Every control there — the token check, the policy, row-level security, approval, audit — acts on a request that has already been made.

Track 8 tests the **control plane**: the artifacts that decide which requests are possible in the first place. Which tools exist. What the model is told they are for. Which services can open a socket to which. Change one of these and the data plane faithfully enforces the new shape — with no request, no decision and no audit row to show that anything changed.

## The architecture

```text
Pull request ──> repository ──┬──> API image         (create_app: which tool routers exist)
                              ├──> action document   (openapi/supportpilot-actions.json)
                              ├──> policy bundle     (policy/supportpilot, copied into OPA at start)
                              └──> compose.yaml      (networks: who can reach whom)

A person ──> Onyx admin panel ──> the agent's registered actions   (pasted from the document)
```

Everything on the first branch goes through a diff. The last line does not: it is a person copying a file into another product's web form, and it is the subject of challenge 8.1.

## The artifacts, and what keeps each one honest

| Artifact | Where it lives | What changes it | What checks it |
|---|---|---|---|
| The tool routers | `create_app` in the API | a merged pull request, then a rebuild | the export audit, when it runs |
| The action document | `openapi/supportpilot-actions.json` | `scripts/export_openapi.py` | `export_openapi.py --check` |
| The agent's registered actions | Onyx's database | a person, in the admin panel | **nothing** |
| The tool descriptions | the route code, copied into the document | a pull request | the export checks that each **exists**, not what it says |
| The policy | `policy/supportpilot/authz.rego` | a pull request, then a restart | its Rego tests in `policy/tests/`, and the verify checks that send it real requests. `policy_version` is a literal typed by hand |
| The network map | `compose.yaml` | a pull request | V-02 and V-17, which open real sockets |

Read the last column carefully. Every entry except one is a check that compares two artifacts, or measures the runtime. None of them asks whether a change was **agreed to** — and the control plane has no proposal, no second approver and no audit row, because those are controls over requests.

## Who may do what?

| Actor | Can | Cannot |
|---|---|---|
| A developer | change any of the files above, through a pull request | change what the running agent holds — that takes an Onyx admin |
| An Onyx admin | paste any document into the agent's actions | change what the API permits: authority is enforced at the boundary |
| The model | choose among the tools it was given | register a tool, change a description, or reach a route that is not in its document |
| External text (tickets, tool results) | nothing on this list | register tools, change policy, or alter instructions (rule 10) |

## What is real in this lab?

The export script, the action document, the network definitions and the checks are the real ones. The Onyx side is real too, but outside the repository, so the Range cannot read it — and that is the point of 8.1, not a gap in it.

Two things in this track are written out as **illustrative code that is not in the repository**: a URL-fetching tool (8.2) and a tool server that changes its answer (8.3). Both are exactly what rule 7 and rule 10 forbid. They appear as text so you can read the shape, and nothing in the lab builds them.

**Next:** what the checks on the control plane actually verify, and where they run.
