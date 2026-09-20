# The one that is different

`search_customers`.

```
get_order            order_number            an identifier
get_customer         customer_ref            an identifier
get_ticket           ticket_number           an identifier
add_internal_note    ticket_number + body    an identifier
propose_refund       order_number in body    an identifier
get_action_status    action_id               an identifier
search_customers     q, limit, cursor        A QUERY
```

Six reach exactly one thing, named in advance. The seventh lets the caller choose the set.

## The worst legal call

> One call with a two-character `q` returns up to twenty-five customer records — and `cursor` makes
> the rest of the directory reachable by repeating the call.

That is the sentence. Note what it does not say: not "risky", not "medium", not "could be abused".
It names the tool, the shape of one call, and the thing that makes repetition matter.

## What is already bounded here, and what is not

Worth being precise, because a finding that ignores existing controls is a finding that gets
dismissed.

| Bounded | How |
|---|---|
| Page size | the policy returns `max_results: 25`; the API clamps. **The caller's `limit=50` is ignored** |
| Fields | the obligation returns `customer_ref`, `full_name`, `assigned_team` — **no email** |
| Tenant | membership, enforced at the API and again by row-level security |

| Not bounded | Consequence |
|---|---|
| Minimum length of `q` | `ab` is a valid search |
| Calls per session | nothing counts them |
| Paging depth | the cursor advances indefinitely |

So the leak is not a page. **It is the product of pages**, and every single call in it is correctly
authorised, correctly scoped, and correctly logged as `allowed`.

This is not hypothetical. This lab's agent, asked in one plain sentence to search for fifteen
two-letter strings, made fifteen authorised calls and returned the customer directory.

## Narrowing it — name which one you mean

A finding without a named remedy is a complaint. There are five ways to narrow a tool, and saying
which is the difference:

| Narrow by | From | To |
|---|---|---|
| resource | `search(q)` | `get(id)` |
| field | the whole record | policy obligations |
| **volume** | **client-chosen** | **a server-set maximum, per call *and* per session** |
| effect | `issue_refund` | `propose_refund` + approval |
| time | a standing approval | one that expires |

For this tool it is **volume**, and specifically the session half: the per-call cap already exists
and does not help. A minimum query length and a per-session ceiling would, and both are
configuration rather than architecture.

## What this surface gets right, and why it matters to say so

Look at what is *absent*, because the absences are the design:

- **No `issue_refund`.** Only `propose`, which cannot move money.
- **No `search_orders`, no `list_customers`.** A query exists in exactly one place.
- **No `get_customer_by_email`.** A reverse lookup is a verification oracle.
- **No `fields=` or `include=*`.** The field set comes from policy, not from an argument.
- **Nothing that sends anything outside the system.** The composition table has no right-hand column.

That last one is the big one. Most of tool-authority review is pairing a broad read with any write
that leaves — and here there is nothing to pair with.

> **Say what is right as well as what is wrong.** A reviewer who only lists problems teaches a team
> nothing about which of their decisions to keep, and gets read as someone who did not look.

## Take it to a review

1. **Show me the registered tool list** — the registration, not the descriptions.
2. For each: **the worst legal call, in one sentence.**
3. **Which take a query rather than an identifier?** For each: who sets the page size, is there a
   minimum query length, is there any ceiling per session?
4. **Any parameter typed `object` with no schema?**
5. Draw two columns — **what comes into the model's context, what leaves** — and look at the pairs.

Question 3 is the one this challenge is about, and question 5 is the one that finds what nobody
reviewed, because every tool is defensible alone.
