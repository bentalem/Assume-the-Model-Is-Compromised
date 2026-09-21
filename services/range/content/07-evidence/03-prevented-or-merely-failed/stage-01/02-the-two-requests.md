# The two requests

Both of these are made by alice, a support agent in the cedar tenant, and both are refused. The
first two buttons in the console issue them — the real requests, through the real API, as her — and
what is printed below is what they produce.

**Make them both before you go near the trail.** Until you do, the trail has nothing to say about
either of them, and that is not the absence this challenge is about.

## Request A

```
GET /v1/orders/ORD-3001                                 404
```

`ORD-3001` is a real order. It belongs to **northwind**, the other tenant.

## Request B

```
POST /v1/actions/refunds                                400
{"level":"INFO","logger":"supportpilot","event":"request_rejected",
 "path":"/v1/actions/refunds",
 "rejected":[{"field":"body.reason","error":"enum"}]}
```

A refund proposal on an order alice is fully entitled to propose a refund for. The body carried a
`reason` of `"damaged item"`, where the schema declares an enumeration.

---

## What each one looks like from outside

Neither response says which part of the system refused. The `404` says nothing at all, deliberately —
one that distinguished "belongs to someone else" from "does not exist" would answer the question an
attacker is asking. The `400` is more forthcoming: it names the offending field and the kind of
failure, in the body as well as in the log, because a caller that cannot see which field it got wrong
cannot correct it. What neither of them tells you is whether a control was consulted.

So both are refusals, and a report written from the responses alone would call both of them blocked.

## What to do instead

Open the trail. For each request, ask one question:

> **Is there a decision row for this attempt?**

Then, for whichever one has a row, ask the second question:

> **Does it carry a policy version?**

The three audit observations in the console are enough. One shows every decision recorded about
`ORD-3001`; one shows the same for `ORD-2001`, which alice may read, so you can see what an ordinary
row looks like; and one shows the last thirty decisions from the whole system, which is where you go
to confirm that something is **not** there.

That last one is the awkward search, and it is the one worth practising: looking for an absence is
harder than looking for a row, and it is what an investigation actually consists of.

## The answer you are giving

Not "A was blocked". The **reason code** that the control recorded when it refused it — the string
in the `reason` column. That is what you would quote in a finding, because it is the thing a reader
can go and look up for themselves.
