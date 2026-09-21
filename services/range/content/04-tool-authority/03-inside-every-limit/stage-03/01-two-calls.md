# Two calls

That is the number that makes this challenge worth doing.

```
calls                  2
distinct_records       30
every_call_allowed     yes
more_pages_remaining   no
```

This tenant has 33 customers. A two-character query matched 30 of them, and **two authorised
requests reached every one**. The cursor came back empty because there was nothing left — the
directory was exhausted, not truncated.

Both calls were inside the 25-record cap. Both were correctly authorised. Both were recorded as
`allowed`, with a policy version, by a control that was working exactly as designed.

## What you would write in a report

Not "the search tool is vulnerable". It is not. Try instead:

> `search_customers` accepts a query of any length and returns up to 25 records per call, with a
> cursor. Nothing limits calls per session, so the full customer directory of a tenant is reachable
> in as many calls as it takes — two, here. Every call is correctly authorised and logged as
> allowed, so neither the authorization layer nor the audit trail will show anything unusual.

Three things make that sentence land where "this tool is risky" does not:

1. **It names the mechanism.** A reader can check it in five minutes.
2. **It concedes what works.** The per-call cap is real and the fields are minimised. A finding that
   ignores existing controls gets dismissed by the person who built them.
3. **It says what monitoring will not show.** That is the part that changes what a team does next.

## The distinction worth keeping

| | Per call | Per session |
|---|---|---|
| Who sets it | the policy, and the API clamps | nobody |
| What it bounds | one response | the total a conversation can obtain |
| What it survives | a caller asking for more | nothing — it does not exist |

A per-call cap answers *"how much can one request return?"* A per-session ceiling answers *"how much
can one actor obtain?"* Only the second is a limit on extraction, and teams routinely believe they
have the second because they can point at the first.

## Why an agent changes the arithmetic

A person paging a UI thirty times is doing something visibly odd. It takes minutes, it is tedious,
and somebody would have to mean it.

The same thirty calls from an agent take a second and look like one request from the outside,
because from the outside there *was* one request — somebody typed a sentence. The tool did not gain
any authority it did not have when a human was clicking. **What changed is the rate, and the rate is
the dimension nobody rates.**

That is the whole of track 4's third dimension, arriving as a number rather than an argument.

## What would actually fix it

Two changes, both configuration rather than architecture, and it is worth naming which does what:

- **A longer minimum query length.** There is already one — the schema declares `minLength: 2` —
  and two characters reached 30 of 33 records, so it is currently a control in name only. Raising
  it raises the cost of a blind sweep and no more: a determined caller enumerates the alphabet.
  Describe it as the speed bump it is.
- **A per-session or per-token record ceiling.** This is the control. It bounds the total, which is
  the quantity the finding is about, and it is the one that does not exist here.

Do not recommend rate limiting by itself. Rate limiting bounds calls per second; the attacker is
happy to go slowly, and an agent is happy to wait.

## Take it to a review

1. **"Which of your tools takes a query rather than an identifier?"** Those are the bulk-read
   primitives, whatever their names suggest.
2. **"Who sets the page size — the caller or the server?"** Then: is it clamped, or just a default?
3. **"What bounds the number of calls in one session?"** The most useful silence in this list.
4. **"Show me the audit trail for a full enumeration."** If it looks identical to normal traffic,
   that is the finding, and it is worth stating that the trail is correct and still unhelpful.
5. **"What would you alert on?"** If the answer is denials, point out that this leaves none.

Question 3 is the one that transfers to every system you will ever review, and it takes one
sentence to ask.
