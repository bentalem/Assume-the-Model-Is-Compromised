# All closed. Not all visible.

`policy_malformed`.

Here is the table you built:

```
                      engine     HTTP    audit reason          policy_version
stop it               stopped    503     policy_unavailable    (none)
make it error         running    503     policy_unavailable    (none)
move the decision     running    404     policy_malformed      (none)
```

Three ways to break the thing that decides. **Three denials.** Nothing was authorized, no data was
returned, and every one of them was recorded. That is the control working, and it is worth saying
before anything else, because the rest of this page is about a subtlety and not about a failure.

## The third row is different in the way that matters

The first two announce themselves. `503` is a word the whole industry agrees on: something I depend
on is broken. Every dashboard has a panel for it. Every on-call rotation has an alert on it.

The third returns `404`.

To the caller, that is *"there is no such order"* — the same answer alice would get for an order
number somebody typed wrong. To a dashboard, it is a rounding error in a metric that is noisy
anyway. Nobody pages anybody about a 404.

And the engine was **healthy the whole time**. It was running, it was answering, its own health
check passed. Anything monitoring the decision point saw a perfectly good service.

> The system was refusing every request and correctly recording why, and the only place that said so
> was a reason code in a table nobody was watching.

## Why it comes out that way, and why the code is not wrong

One line decides it, and it is in the source panel:

```
raise unavailable() if decision.unavailable else not_found()
```

The client sets `unavailable` for a dependency failure — timeout, unreachable, bad status. It does
*not* set it for a malformed or undefined answer, and that is a defensible reading: a response that
parsed but contained no decision is not obviously the dependency being down. It might be a bad
deployment. It might be a policy that was never written.

And the `404` is deliberate elsewhere for a good reason — this API answers `404` rather than `403`
so that a refusal never confirms a resource exists in another tenant. That is the right call and it
is the reason the fallback branch looks the way it does.

So this is not a bug with an obvious fix. It is a **gap between two correct decisions**, which is
where most real findings live. The finding is not "the code is wrong". It is:

> **Your policy engine has failure modes your alerting cannot see.** Three of the five report as a
> dependency outage. Two of them do not.

## The trap this is really about

Go back to the fail-open story. Somebody adds a cache because the engine flapped.

Now ask: how would you ever know if that cache was serving stale allows? You would look for
outages — and find none, because the engine was up. You would look at error rates — and find none,
because everything returned 200. You would look at the audit trail — and every row would say
`allowed`, with a policy version, from a real decision that was simply made earlier.

**A fail-open system under a failure it is designed to absorb produces no signal at all.** That is
not a side effect of failing open; it is the whole of what failing open means.

Which is why the question to ask is never "do you fail closed". Everybody says yes. The question is:

> **"Show me what the last policy outage looked like in your logs."**

If they can find it, they fail closed and they can see it. If there is nothing to find, that is
either a system that has never had an outage, or a system where an outage leaves no trace. Only one
of those is good news, and you can tell which by breaking it on purpose — which is what you just did.

## Take it to a review

1. **"Read me every branch in the policy client that returns without a decision."** Count them.
   There are usually more than the author remembers.
2. **"Which of those does the caller see as a dependency failure?"** The rest are invisible to
   operations.
3. **"What happens on an undefined decision?"** The single most revealing line. Deny, or a missing
   key treated as absent-and-therefore-fine.
4. **"Is there a cache, a default, or a last-known-good anywhere in this path?"** Ask about the
   resilience work, not about the authorization work — that is the name it will have been done under.
5. **"Show me the last policy outage in your logs."** Then ask what the users saw.

**Reset before you leave**, and check the bundle state reads `correct` for all four. A challenge in
this track that leaves the engine broken makes every measurement in every other challenge a
measurement of that.
