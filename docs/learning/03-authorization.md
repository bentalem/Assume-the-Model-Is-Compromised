# Authorization: the system behind track 3

This is the same architecture lesson shown in challenge 3.1's three opening Learn tabs. Read it before starting track 3. No terminal is needed for the challenges.

## 1. Start here: how authorization is decided

Read these three architecture tabs before you start challenge 3.1. They explain the part of the system track 3 is about: who asks "may this person do this?", who answers, and what happens when the answer does not come.

Two terms carry the whole track:

| Term | What it is | In this lab |
|---|---|---|
| **Policy decision point (PDP)** | the component that answers "allowed or not, and why" | **OPA**, running the rules in `policy/supportpilot/authz.rego` |
| **Policy enforcement point (PEP)** | the component that asks, then carries out the answer | **the API** — every tool call goes through its `pipeline.py` |

The decision and its enforcement live in different processes on purpose. The rules can be read, tested and changed under review without touching the API — and the API is the only thing that can act on them.

## The architecture

```text
Agent runtime
    |  tool call, with the user's token
    v
SupportPilot API  (the enforcement point)
    |-- 1. verify the token, load the person         (track 1)
    |-- 2. load the record, under row security       (track 2)
    |-- 3. build the policy input
    |
    |------ POST input ----->  OPA  (the decision point, on the "policy" network)
    |<----- decision --------     allow · reason · policy version · obligations
    |
    |-- 4. deny?  -> write an audit row, refuse
    |-- 5. allow? -> query, apply obligations, audit, respond
```

OPA sits on its own internal network, `policy`, and the API is its only client. `V-02` proves nothing on the edge network can reach it.

## Who is allowed to do what?

| Component | Can | Cannot |
|---|---|---|
| The model | choose a tool and its arguments | reach OPA, or put anything into the policy input |
| The API | build the input from verified identity and loaded records; enforce the answer | decide on its own, or treat a missing answer as yes |
| OPA | evaluate the rules against the input | read the database, or enforce anything |
| The rules | say allow or deny, why, and with what conditions | see anything the API did not put in the input |

## What is real in this lab?

OPA and the rules are the real ones. The rules live in `policy/supportpilot/`, with their own tests in `policy/tests/` (`opa test policy/`). At start-up a one-shot container, `opa-bundle-init`, copies them into a volume OPA loads from.

The Range reaches this layer in two ways, both reversible: it can **stop the OPA container** through the Docker proxy (3.1, 3.4), and it can write a **modified bundle** to that volume (3.3, 3.4). A modified bundle is always derived from the real policy file at the moment you arm it — there is no second, hand-written policy anywhere in the repository to drift out of date.

**Next:** exactly what the API asks, and what the answer contains.

## 2. Part 1: the question and the answer

## The question: the policy input

For every tool call, the API sends OPA one JSON document with four parts. Everything in it comes from the verified token or from a server-side lookup — nothing comes from the model's arguments.

| Part | Contains | Comes from |
|---|---|---|
| `subject` | the person's id, their organisations, their roles **in the record's tenant**, their authentication level | the token's `sub`, then `app.memberships` (track 1) |
| `action` | one of eight fixed names | the route that was called |
| `resource` | the record's tenant, type, id, and attributes such as `sensitivity` or `requester_id` | the database, loaded **before** the question is asked (track 2) |
| `context` | the request id, the time, the network zone | the API itself |

The eight actions: `order.read`, `customer.read`, `customer.search`, `ticket.read`, `note.create`, `refund.propose`, `refund.approve` and `action.read`.

## The answer: the decision

The rules return one document, and the API accepts it only if every part has the right type:

| Field | Meaning | Example |
|---|---|---|
| `allow` | exactly `true` or `false` — not `"true"`, not `1` | `true` |
| `reason` | why, as a stable code | `same_organization_and_allowed_role` |
| `policy_version` | which version of the rules decided | `2026-09-28.1` |
| `obligations` | conditions attached to an allow | `{"allowed_fields": [...]}` |

Two obligations exist in this lab:

- **`allowed_fields`** — "yes, and only these fields". The API removes every other field between the query and the response. Challenge 3.2.
- **`max_results`** — a page-size cap on searches, which the API applies to the query. Challenge 4.1.

## Deny by default, written down

The first rule in the file is not an allow. It is the answer when nothing else matches:

```rego
default decision := {
    "allow": false,
    "reason": "default_deny",
    "policy_version": "2026-09-28.1",
}
```

Every allow below it has to state its own reason. A deny carries a reason and the policy version too, and both end up in the audit row — so every refusal the rules make can be traced to the exact rules that made it.

## What the API does with the answer

| The decision | Audit row | The caller gets |
|---|---|---|
| allow | `allowed`, the reason, the policy version | the data — minus any field not in `allowed_fields` |
| deny from the rules | `denied`, the reason, the policy version | `404`, the same as for a record that does not exist |

`404` rather than `403` is deliberate: a refusal must never confirm that a record exists in another tenant.

**Read the code:** `policy/supportpilot/authz.rego`, `services/api/src/supportpilot_api/pipeline.py`.

## 3. Part 2: when no answer comes

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
