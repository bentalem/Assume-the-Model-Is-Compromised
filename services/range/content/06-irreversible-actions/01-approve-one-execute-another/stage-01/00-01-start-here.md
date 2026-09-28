# Start here: how a refund actually happens

Read these two architecture tabs before you start challenge 6.1. They explain the part of the system track 6 is about: the only path in this lab by which money can move, and the three different parties it passes through.

The rule behind the whole design: **the model may propose. A person decides. A separate process executes, once.** No single component can do more than one of the three.

## The architecture

```text
1. PROPOSE      the model calls propose_refund (a tool), in alice's session
                -> API: validates, freezes the payload, hashes it
                -> app.action_requests   state PENDING_APPROVAL, expires in 24 hours
                   nothing has moved

2. APPROVE      fiona (finance_approver) opens the approval portal
                -> portal: shows the exact frozen payload and its sha256
                -> API /internal/approvals/{id}   (not a tool — the model cannot reach it)
                -> app.approval_decisions   records approved_hash, a second copy of the hash
                -> app.action_jobs   one job queued for the request

3. EXECUTE      the worker claims the job
                -> re-checks everything, recomputes the hash
                -> reserves an idempotency key as 'ambiguous'
                -> calls the refund provider
                -> app.action_executions   records the outcome
```

## Who is allowed to do what?

| Component | Can | Cannot |
|---|---|---|
| **The model** | call `propose_refund` | approve, execute, or choose where money goes — the payload has no destination field |
| **The API** | create a pending request; record a decision made by an approver | perform the refund — it never calls a provider |
| **The approval portal** | render the payload and its hash; forward the approver's decision | decide anything itself, or edit a payload |
| **The approver** (`finance_approver`) | approve or reject the exact payload hash they were shown | approve their own request |
| **The worker** (`sp_worker_role`) | claim a job, verify it, execute it once | read customers or orders; take instructions from a model |

## The four tables

| Table | One row is | The rule that keeps it honest |
|---|---|---|
| `app.action_requests` | one proposed refund: frozen payload, `payload_hash`, requester, state, `expires_at` | the hash is computed once, at proposal |
| `app.approval_decisions` | one approver's decision, with `approved_hash` | `one_decision_per_request`; a trigger refuses requester = approver |
| `app.action_jobs` | the queued work for one request | `one_job_per_request` |
| `app.action_executions` | one effect, under one idempotency key | `one_effect_per_key` |

## What is real in this lab?

All of it except the money. The worker runs `FakeRefundAdapter`, which applies refunds to a dictionary in memory; the adapter for a real provider refuses any host that is not on its allowlist, and has no provider chosen yet. Every check, every table and every refusal on the way there is the real one.

**Next:** what the worker checks before it acts, and which challenge breaks each check.
