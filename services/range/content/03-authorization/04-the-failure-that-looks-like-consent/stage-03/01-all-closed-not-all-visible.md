# All closed. Not all visible.

## What your result proves

`policy_malformed`.

```
                      engine     HTTP    audit reason          policy_version
stop it               stopped    503     policy_unavailable    (none)
make it error         running    503     policy_unavailable    (none)
move the decision     running    404     policy_malformed      (none)
```

Three ways to break the thing that decides. **Three denials.** Nothing was authorized, no data was returned, and every one of them was recorded. That is the control working — the rest of this page is about a subtlety, not a failure.

The first two announce themselves. `503` is a word the whole industry agrees on: something I depend on is broken. Every dashboard has a panel for it. The third returns `404` — to the caller, *"there is no such order"*, the same answer as a mistyped order number. Nobody pages anybody about a 404. And the engine was **healthy the whole time**: running, answering, passing its own health check.

> The system was refusing every request and correctly recording why, and the only place that said so was a reason code in a table nobody was watching.

## Where the control lives

In `policy/client.py`, which has a separate branch for every way an answer can fail, and every branch denies. It marks three of them — a timeout, an unreachable engine, an error status — as a **dependency failure**. It does not mark an unparseable or undefined answer that way, and that is a defensible reading: a response that parsed but contained no decision is not obviously the dependency being down. It might be a bad deployment. It might be a policy that was never written.

Then one line in `pipeline.py` decides what the caller sees:

```python
raise unavailable() if decision.unavailable else not_found()
```

And the `404` is deliberate for a good reason elsewhere: a refusal must never confirm that a resource exists in another tenant. So this is not a bug with an obvious fix. It is a **gap between two correct decisions** — where most real findings live.

> **Your policy engine has failure modes your alerting cannot see.** Three of the client's branches report as a dependency outage. The others do not.

## What restoring fixes

Restoring puts the real bundle back or starts the engine, and requests are allowed again. Nothing was cached, so nothing stale survives.

What remains is the evidence, and it tells you how to detect the quiet case next time. For the first two failures, anything watching `503`s saw an outage. For the third, **the only record is a run of `policy_malformed` rows** in the audit trail. An alert on that reason code is the whole of the detection for it — and without one, the outage lasts exactly as long as nobody complains.

## Take it to a review

Go back to the fail-open story from Stage 01. Somebody adds a cache because the engine flapped. How would you ever know that cache was serving stale allows? You would look for outages — and find none, because the engine was up. You would look at error rates — and find none, because everything returned 200. You would look at the audit trail — and every row would say `allowed`, with a policy version, from a real decision that was simply made earlier.

**A fail-open system under a failure it is designed to absorb produces no signal at all.** That is not a side effect of failing open; it is the whole of what failing open means. So the question is never "do you fail closed". Everybody says yes. The question is:

> **"Show me what the last policy outage looked like in your logs."**

1. **"Read me every branch in the policy client that returns without a decision."** Count them. There are usually more than the author remembers.
2. **"Which of those does the caller see as a dependency failure?"** The rest are invisible to operations.
3. **"What happens on an undefined decision?"** The single most revealing line. Deny, or a missing key treated as absent-and-therefore-fine.
4. **"Is there a cache, a default, or a last-known-good anywhere in this path?"** Ask about the resilience work, not about the authorization work — that is the name it will have been done under.
5. **"Show me the last policy outage in your logs."** Then ask what the users saw.

**Reset before you leave**, and check the bundle state reads `correct`. A challenge in this track that leaves the engine broken makes every measurement in every other challenge a measurement of that.
