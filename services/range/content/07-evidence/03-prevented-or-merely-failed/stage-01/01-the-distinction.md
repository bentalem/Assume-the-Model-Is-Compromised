# Prevented, or merely failed

Something did not happen. That is the whole of what you observed.

There are two entirely different reasons for it, and they look identical from outside:

**Prevented.** A control evaluated the request and refused it. The control is working, you have
evidence it is working, and you can say so.

**Merely failed.** The request was malformed, or the service was busy, or a field was the wrong type,
and it fell over before any control was consulted. The control was not exercised. **You have learned
nothing about it** — and if you had sent a well-formed version, it might well have succeeded.

> **"It didn't work" and "it was prevented" are different sentences.** Writing the second when only
> the first is true is how a security report dies, because the first engineer who checks will find
> that a correct request goes straight through.

## Why this is the most common error in the field

Because the natural experiment produces it. You try something bad, you get an error, you write
"blocked". Nobody asks *blocked by what*, and the report reads well.

It is also the error most likely to be found by the person you are reporting to, because they have
the logs.

## The three ways a request dies before authorization

| Where it dies | What you see | What it proves about authorization |
|---|---|---|
| Schema validation | `400 invalid_request` | **nothing** |
| Token verification | `401` | that authentication works. Not authorization |
| Resource lookup | `404` | that the caller cannot see the resource exists — which *is* a control |
| Policy | `403`/`404` with a reason | that the rules refused it |
| Row-level security | empty result | that the data layer refused it |

The middle three are all controls and all worth reporting. The first is not a control at all, and it
is the one that gets mistaken for one — because a `400` looks like a refusal and arrives fast.

## The tell is the trail, not the response

You usually cannot distinguish these from the response body. A well-built API returns the same shape
for a cross-tenant read and a non-existent record on purpose: an error that explains which one it was
is an oracle.

So you look at what was **recorded**:

- A request refused by a control has a **decision row**: who, what, the decision, a reason, and
  usually the version of the rules that decided.
- A request that died in schema validation has **no row at all**. There was no subject yet, no
  resource, and nothing to record a decision about.

**The absence is the evidence.** That is the part people find strange and it is the most useful
sentence in this challenge:

> If the attempt you are investigating is not in the audit trail, that is not a gap in the logging.
> It usually means the request never reached the thing that does the logging.

## And a second reading of the same rows

Once you have found the row, look at the **policy version**.

A denial that carries one was refused by policy. A denial with no version was refused earlier — by
the resource lookup, before policy was ever asked, because the caller could not see that the record
existed.

From outside, both are an identical 404. Inside, they are different layers, and only the reason code
tells you which one acted. Reporting "policy blocked it" when the resource lookup did is a smaller
version of the same mistake this whole challenge is about.
