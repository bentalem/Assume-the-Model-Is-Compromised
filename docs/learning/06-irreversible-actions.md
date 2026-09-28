# Irreversible actions: the system behind track 6

This is the same architecture lesson shown in challenge 6.1's two opening Learn tabs. Read it before starting track 6. No terminal is needed for the challenges.

## 1. Start here: how a refund actually happens

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

## 2. Part 1: the last checks before the money moves

The worker is the last component before an irreversible act, so it trusts nothing that came before it. Its `verify()` method in `services/worker/src/supportpilot_worker/jobs/processor.py` re-checks everything, in this order, and refuses at the first failure:

| # | The check | Reason code if it fails | Catches |
|---|---|---|---|
| 1 | the request's state allows execution | `action_state_forbids_execution:<state>` | a request that was rejected, cancelled or already finished |
| 2 | an approval decision exists | `no_approval_decision` | a job with nobody's approval behind it |
| 3 | the decision was an approval | `action_was_<decision>` | a rejected request |
| 4 | the approver is not the requester | `self_approval_detected` | separation of duty, checked once more |
| 5 | the approval window is still open | `approval_expired` | an old approval executed late |
| 6 | the hash of the payload about to be sent equals the stored `payload_hash` | `payload_hash_mismatch_stored` | a payload edited after it was proposed |
| 7 | the approval's `approved_hash` equals the stored `payload_hash` | `payload_hash_mismatch_approved` | an approval moved to a different request |

Only when all seven pass does it reserve the idempotency key and call the provider.

## Checked more than once, on purpose

Several of these rules are enforced in more than one place, by different mechanisms:

| Rule | Where it is enforced |
|---|---|
| The requester may not approve | the policy (`refund.approve`), a database trigger, and the worker — and the approval row policy only accepts a decision recorded under the approver's own id, by a `finance_approver` |
| The approval window | the policy, the approval row policy (against the database's clock), and the worker (against its own clock) |
| The exact payload | the approver sees its hash; the decision records it; the worker recomputes it |
| Exactly one effect | one decision per request, one job per request, one effect per idempotency key |

Each extra place covers a path the others do not — a direct write to the database, a script instead of the portal, a job that sat in a queue. Track 6 is about which of those places actually holds when the others are bypassed.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 6.1 | If the payload changes after approval, which check stops it? |
| 6.2 | When the requester tries to approve their own refund, which layer refuses — and would still refuse with the others gone? |
| 6.3 | A provider call timed out. What makes the retry harmless? |
| 6.4 | The approval is genuine and nothing else changed. Why is it refused anyway? |

**Read the code:** `database/migrations/0008_actions.sql`, `services/worker/src/supportpilot_worker/jobs/processor.py`, `services/api/src/supportpilot_api/internal/approvals.py`.

**Now start challenge 6.1.**
