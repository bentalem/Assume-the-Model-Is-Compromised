# Nothing else changed

`approval_expired`.

```python
if requester == decision["approver_id"]:
    raise RefusedToExecute("self_approval_detected")
if job.expires_at < datetime.now(UTC):
    raise RefusedToExecute("approval_expired")

recomputed = payload_hash(job.payload)
...
```

Look at what was **not** wrong.

| | |
|---|---|
| The payload | unchanged — 45.00, exactly as proposed |
| The hash | matches, both ways |
| The approver | a different person from the requester |
| The request state | still `PENDING_APPROVAL` |
| The approval itself | genuine, attributable, recorded |

Every other control in the chain was satisfied. The only thing wrong was **when**.

That is what makes this control different in kind from the other three. Separation of duty is about
*who*. Payload binding is about *what*. Expiry is about *when* — and time is the one input that
changes without anybody doing anything.

> The other controls refuse things somebody did. This one refuses something that happened by
> **nobody** doing anything for long enough.

## Which is why it is the one that gets left out

Every control in the chain has a visible attacker in its story except this one. Self-approval has a
fraudulent employee. Payload tampering has someone editing a row. Expiry has… a slow queue.

So it reads as an operational nicety rather than a control, it gets a `TODO`, and the system ships
with approvals that are valid forever. Then the provider has a bad afternoon, two hundred approved
actions sit in a queue overnight, and the window during which any of them could be replayed is
exactly as long as the outage.

## Three orderings, and only one is right

Notice where the check sits: **inside the worker, immediately before the provider call**, alongside
the other two.

| Where expiry is checked | What it stops |
|---|---|
| when the approval is recorded | approving something stale. Not executing something stale |
| when the job is queued | a request that was already late. Not one that became late while queued |
| **immediately before execution** | **everything above, and the queue delay itself** |

The first two are the versions people build, and both leave the gap that matters. The deadline has
to be evaluated against the moment of the irreversible act, because that is the moment the approver
was implicitly making a statement about.

## Writing it up

```
Approvals for <action> carry an expiry, but it is evaluated when the approval is
recorded rather than before execution. An approved action that remains queued past
its window — after a provider outage, a failed deploy, or a retry backlog — will
execute on a judgement that has expired.

Demonstrated: an approved request whose window had closed was still executable.

Fix: evaluate expires_at in the worker, immediately before the provider call,
against the database clock rather than the worker's.
```

The last clause is worth keeping. **Ask whose clock.** A deadline evaluated on the machine that
wants to proceed is a deadline that machine can be wrong about, and clock skew in a container fleet
is not exotic.

**Reset before you leave** — the window is currently in the past, and a lab left in that state will
make the next thing you measure confusing.
