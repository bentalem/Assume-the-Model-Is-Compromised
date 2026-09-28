# Two calls

## What your result proves

That is the number that makes this challenge worth doing.

```
calls                  2
distinct_records       30
every_call_allowed     yes
more_pages_remaining   no
```

This tenant has 33 customers. A two-character query matched 30 of them, and **two authorised requests reached every one**. The cursor came back empty because there was nothing left — the directory was exhausted, not truncated.

Both calls were inside the 25-record cap. Both were correctly authorised. Both were recorded as `allowed`, with a policy version, by a control that was working exactly as designed.

## Where the control lives

The control that exists is per call, and it is real:

1. **The policy** returns `max_results: 25` with every allowed search.
2. **The API** clamps the page size in `pagination.py`: the lower of what the caller asked for, the endpoint's own maximum, and the policy's number. A caller asking for `limit=50` gets 25.
3. **The field obligation** removes everything but `customer_ref`, `full_name` and `assigned_team` before the response is built.

| | Per call | Per session |
|---|---|---|
| Who sets it | the policy, and the API clamps | nobody |
| What it bounds | one response | the total a conversation can obtain |
| What it survives | a caller asking for more | nothing — it does not exist |

A per-call cap answers *"how much can one request return?"* A per-session ceiling answers *"how much can one actor obtain?"* Only the second is a limit on extraction, and teams routinely believe they have the second because they can point at the first.

## What this check does not cover

Nothing counts calls. Nothing totals records across a session. The minimum query length — `minLength: 2` in the schema — is a control in name only: two characters reached 30 of 33 records.

Why an agent changes the arithmetic: a person paging a UI thirty times is doing something visibly odd. It takes minutes, it is tedious, and somebody would have to mean it. The same calls from an agent take a second and look like one request from the outside — because from the outside there *was* one request: somebody typed a sentence. **What changed is the rate, and the rate is the dimension nobody rates.**

What would actually fix it, both configuration rather than architecture:

- **A longer minimum query length.** It raises the cost of a blind sweep and no more: a determined caller enumerates the alphabet. Describe it as the speed bump it is.
- **A per-session or per-token record ceiling.** This is the control. It bounds the total, which is the quantity the finding is about.

Do not recommend rate limiting by itself. Rate limiting bounds calls per second; the attacker is happy to go slowly, and an agent is happy to wait.

## Take it to a review

Not "the search tool is vulnerable". It is not. Try instead:

> `search_customers` accepts a query of any length and returns up to 25 records per call, with a cursor. Nothing limits calls per session, so the full customer directory of a tenant is reachable in as many calls as it takes — two, here. Every call is correctly authorised and logged as allowed, so neither the authorization layer nor the audit trail will show anything unusual.

Three things make that sentence land where "this tool is risky" does not: **it names the mechanism**, so a reader can check it in five minutes; **it concedes what works**, because a finding that ignores existing controls gets dismissed by the person who built them; and **it says what monitoring will not show**, which is the part that changes what a team does next.

1. **"Which of your tools takes a query rather than an identifier?"** Those are the bulk-read primitives, whatever their names suggest.
2. **"Who sets the page size — the caller or the server?"** Then: is it clamped, or just a default?
3. **"What bounds the number of calls in one session?"** The most useful silence in this list.
4. **"Show me the audit trail for a full enumeration."** If it looks identical to normal traffic, that is the finding — and it is worth stating that the trail is correct and still unhelpful.
5. **"What would you alert on?"** If the answer is denials, point out that this leaves none.
