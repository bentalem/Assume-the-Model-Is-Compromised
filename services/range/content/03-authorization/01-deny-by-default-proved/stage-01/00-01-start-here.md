# Start here: how authorization is decided

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
