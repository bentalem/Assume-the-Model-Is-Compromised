# History is a cache of authorised answers

In 1.3, bob was demoted and his very next request to the API came back without the customer's email.
The API loads his roles on every request, so the demotion took effect at once.

Now put history in between.

```
09:00  bob (manager)  get_customer CUS-4003   → email shown, because he may see it
09:00  runtime        stores the tool turn in bob's session
10:00  bob is demoted to support_agent
10:05  bob            "prepare the escalation call"
       runtime        rebuilds context — including the 09:00 tool turn
```

At 10:05 the API would refuse bob that email. The history does not ask the API. It replays what was
stored, and the email reaches the model in bob's context as if nothing had changed.

That is a cache with no invalidation — the same shape as roles read from a token, which 1.3 was
about. The source of truth changed; the copy did not.

## What re-authorisation on replay means

Every turn this service stores records **the roles it was produced under**, captured from the
verified principal at write time. When history is replayed into context, a tool or assistant turn
produced under a role the caller no longer holds is **left out** — and the block says that it was,
so the omission is not silent.
