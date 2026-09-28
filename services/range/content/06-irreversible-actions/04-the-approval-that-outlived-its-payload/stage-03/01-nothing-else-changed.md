# Nothing else changed

## What your result proves

`approval_expired`.

```python
if decision["approver_id"] == job.requester_id:
    raise RefusedToExecute("self_approval_detected")
if job.expires_at < datetime.now(UTC):
    raise RefusedToExecute("approval_expired")

recomputed = payload_hash(job.payload)
...
```

Look at what was **not** wrong:

| | |
|---|---|
| The payload | unchanged — 45.00, exactly as proposed |
| The hash | matches, both ways |
| The approver | a different person from the requester |
| The request state | still `PENDING_APPROVAL` |
| The approval itself | genuine, attributable, recorded |

Every other control in the chain was satisfied. The only thing wrong was **when**. Separation of duty is about *who*. Payload binding is about *what*. Expiry is about *when* — and time is the one input that changes without anybody doing anything.

> The other controls refuse things somebody did. This one refuses something that happened by **nobody** doing anything for long enough.

## Where the control lives

**Inside the worker, immediately before the provider call**, alongside the other checks — and the position is the whole point:

| Where expiry is checked | What it stops |
|---|---|
| when the approval is recorded | approving something stale. Not executing something stale |
| when the job is queued | a request that was already late. Not one that became late while queued |
| **immediately before execution** | **everything above, and the queue delay itself** |

The deadline has to be evaluated against the moment of the irreversible act, because that is the moment the approver was implicitly making a statement about.

This lab checks the same deadline in three places, against two clocks. The policy compares the request time with `expires_at` when an approver acts — the API's clock. The approval row policy adds `r.expires_at > now()` — the database's clock. The worker compares `job.expires_at < datetime.now(UTC)` — **its own clock**, in the process that wants to proceed.

## What restoring fixes

Restoring moves the window back into the future, and the request is approvable and executable again. Nothing was executed while it was in the past, and nothing is left behind.

Which is exactly why this is the control that gets left out. Every other control in the chain has a visible attacker in its story. Self-approval has a fraudulent employee. Payload tampering has someone editing a row. Expiry has… a slow queue. So it reads as an operational nicety, it gets a `TODO`, and the system ships with approvals that are valid forever. Then the provider has a bad afternoon, two hundred approved actions sit in a queue overnight — a provider outage, a deploy, a lost lease, a batch that only runs on Monday — and the window during which any of them could be replayed is exactly as long as the outage.

## Take it to a review

Not "do approvals expire". Ask:

> **How long is an approval valid for, and what happens to one that is still queued when it runs out?**

The second half is where the answers get interesting. Systems that expire approvals *at approval time* but not *at execution time* are common, and they have a window exactly as long as their longest outage.

```
Approvals for <action> carry an expiry, but it is evaluated when the approval is
recorded rather than before execution. An approved action that remains queued past
its window — after a provider outage, a failed deploy, or a retry backlog — will
execute on a judgement that has expired.

Demonstrated: an approved request whose window had closed was still executable.

Fix: evaluate expires_at in the worker, immediately before the provider call,
against the database clock rather than the worker's.
```

The last clause is a recommendation, not a description of this lab: here the check guarding execution uses the worker's own clock, while the row policy guarding an approval write uses the database's. So this lab evaluates the same deadline against two different clocks at two different moments, and the one guarding execution is the weaker of the two.

**Ask whose clock.** A deadline evaluated on the machine that wants to proceed is a deadline that machine can be wrong about, and clock skew in a container fleet is not exotic.

**Reset before you leave** — until you do, the window is in the past, and the next thing you measure will be confusing.
