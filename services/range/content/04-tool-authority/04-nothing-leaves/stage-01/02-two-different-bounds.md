# Two different bounds

## The two arguments are not the same kind of thing

| Argument | The question it raises | Answerable per call? |
|---|---|---|
| `customer_ref` | may this caller reach this recipient | yes — identity, tenant, role, row policy |
| `body` | where did these words come from | no |

The first column is access control and this lab is full of it. Membership is checked at the API and
again by row-level security; the policy decides; the trail records it. A recipient argument is the
same shape as `customer_ref` on `get_customer`, so it inherits whatever refuses a cross-tenant
`get_customer` today — which is a thing you can run rather than assume.

The second question has no layer. It is not a question about permission at all — it is a question
about where the content in this call came from, and that history lives in the session, not in the
call.

> **The recipient bound says who may receive. It does not say what may be in it.** Those are
> independent, and only one of them is checked.

## Why per-call authorization structurally cannot close it

Open the first source panel. It is the complete policy input: subject, action, resource, context.
Four keys. The subject is the verified user, the resource is the trusted row the API loaded, the
context is a request id, a timestamp and a network zone.

The request body is not there. Neither is anything the caller read a moment ago.

So the decision for `send_customer_email(CUS-4002, ...)` is computed from exactly the same facts
whether the body contains an order status or the contents of `CUS-4001`'s record. There is no
argument you could add to the rego file to tell those apart, because the rule is not given the thing
that differs.

This is not a bug in the policy. It is what per-call authorization is:

> **Permission is evaluated per call. Composition happens across calls.** 4.1 said your findings
> live in that gap; this is the gap at its widest, because the second call is the one that leaves.

## The pairing

Read a tool surface twice. Once down the left — what puts data into the model's context — and once
down the right — what takes data out of it. Then read the pairs, because every tool on both lists is
defensible on its own and the finding is never in a single row.

| In | Out | What the pair is |
|---|---|---|
| `get_customer` | `send_customer_email` | one record, delivered to a different one |
| `search_customers` | `send_customer_email` | the directory, one message at a time |
| `get_ticket` | `send_customer_email` | a tool steered by text, and a tool that delivers |

That third row is the one that makes this a track-4 problem rather than a data-handling problem. A
ticket contains text written by somebody outside this organisation. Read it and it is in context.
Compose a body and the same session that read it writes it. Every call along the way is permitted.
