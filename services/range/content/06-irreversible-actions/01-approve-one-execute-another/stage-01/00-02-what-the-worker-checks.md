# Part 1: the last checks before the money moves

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
