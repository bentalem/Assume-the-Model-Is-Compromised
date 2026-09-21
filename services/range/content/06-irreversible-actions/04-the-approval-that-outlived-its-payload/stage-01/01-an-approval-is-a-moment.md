# An approval is a moment

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
