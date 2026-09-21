# Whose clock

## Where the deadline is checked, and against whose clock

Three places in this lab, against two different clocks, and the difference matters:

- **Policy, when an approver acts.** It compares `input.context.occurred_at` against
  `input.resource.expires_at`. That is **the API's clock**, at the moment it built the policy input.
- **The row policy, on the same action.** The insert that records a decision carries
  `AND r.expires_at > now()` — so even with the policy engine bypassed, the write is refused, and
  refused against **the database's clock**. Note where it is *not*: the lookup that fetches the
  request by id selects `expires_at` and does not filter on it, which is why the check has to live
  on the write rather than the read.
- **The worker, when it executes.** Immediately before the provider call, in the same block as
  separation of duty and payload integrity.

The first two prevent a *new* approval on a stale request. Only the third stops an *old* approval
from being executed late, and it is the one that actually holds the line.

And the clock is the **worker's own** — `job.expires_at < datetime.now(UTC)`, evaluated in the
process that is about to call the provider. Nothing earlier filters on the window either: the claim
query looks only at the lease and the retry count. So that one comparison is the whole of the
execution-time check, and a container with a skewed clock is a container that can decide a window is
still open. When you review this pattern elsewhere, ask whose clock: a deadline evaluated on the
machine that wants to proceed is a deadline that machine can be wrong about — including this one.

## The question to ask a client

Not "do approvals expire". Ask:

> **How long is an approval valid for, and what happens to one that is still queued when it runs
> out?**

The second half is where the answers get interesting. Systems that expire approvals *at approval
time* but not *at execution time* are common, and they have a window exactly as long as their
longest outage.

## Reading the check rather than being told about it

The third button in the console lists the worker's pre-execution checks the way they appear in its
source: the condition, the reason code each one raises, and the line. It is a read, not an
evaluation — it cannot tell you which of them is true right now, and it does not try to. The two
observations beside it are what say that.

Seven entries, and the comparison above is one of them. Match the state you armed against the
conditions, and the code you want is on that row.
