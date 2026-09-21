# An approval is a statement about a moment

Somebody looked at a refund for forty-five dollars, decided it was reasonable, and said yes.

What did they actually know when they said it?

- The customer's account was in the state it was in **then**.
- No other refund had been issued for that order **yet**.
- The order had not been disputed, reversed, or flagged **so far**.
- Nothing had happened that would have changed their mind, **as of that minute**.

Every one of those is a fact about a moment. An approval that does not expire keeps asserting all of
them, indefinitely, on the strength of a judgement made when they happened to be true.

> **An approval without an expiry is not an approval. It is a capability**: obtained once, valid
> forever, and sitting in a table waiting for somebody to find it.

## Why the request is still sitting there

This is the part worth thinking about before the security argument, because the ordinary reasons are
what make the window matter.

- The payment provider was down and the job has been retrying.
- The queue backed up behind a deploy.
- A worker crashed mid-lease and the job went back to the front.
- Someone approved it on Friday evening and the provider only accepts batches on Monday.

None of those is an attack. All of them produce **an approved, unexecuted action, hours or days
old** — which is exactly the state an attacker wants and does not need to create, because your
infrastructure makes it for free.

## What the window is protecting against

Two different things, and it is worth keeping them apart:

**Staleness.** The world moved. The customer disputed the charge, another agent already refunded it,
the account was closed. The approval is honest and no longer informed.

**Reuse.** Someone finds an old approved row and arranges for it to execute. Nothing was forged —
the approval is genuine, the approver is real, the hash matches. It is simply being used at a time
its approver never considered.

An expiry handles both without having to tell them apart, which is why it is worth more than it
looks: **it does not require anyone to detect anything.**

## Where the deadline is checked, and against whose clock

Two places in this lab, and the difference matters:

- **When an approver acts.** Not in the query — the lookup fetches the request by id and selects
  `expires_at` without filtering on it. The refusal comes from the policy, which compares
  `input.context.occurred_at` against `input.resource.expires_at`. That is **the API's clock**, at
  the moment it built the policy input.
- **When the worker executes.** Immediately before the provider call, in the same block as
  separation of duty and payload integrity.

The second is the one that actually holds. The first prevents a *new* approval on a stale request;
only the second stops an *old* approval from being executed late.

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
