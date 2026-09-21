# Two arguments, two questions

Challenge 4.1 listed the absences on this surface and gave one of them the last word:

> Nothing that sends anything outside the system. The composition table has no right-hand column.

This challenge is that column. What a delivery tool would look like, what a review of one reliably
gets right, what it reliably misses, and why this lab does not have one.

## The shape

Here is the specimen. It is not in this repository — establishing that is half the work below — so
read it as a schema you have been handed in a review.

```
  post:
    operationId: send_customer_email
    summary: Email one of your own customers
    requestBody:
      content:
        application/json:
          schema:
            type: object
            additionalProperties: false
            required: [customer_ref, subject, body]
            properties:
              customer_ref:
                type: string
                pattern: "^CUS-[0-9]{4,12}$"
              subject:
                type: string
                maxLength: 200
              body:
                type: string
                maxLength: 10000
```

Nothing here is sloppy. `additionalProperties` is `false`. The recipient is an identifier with a
pattern, not an address — there is no way to type `attacker@example.com` into it. The address is
looked up server-side from the customer record, so the tool can only reach customers this tenant
already has. Both strings have a length.

It breaks none of the shape rules in this repository's own document audit. It would be stopped once,
for not being on the approved operation list, which is exactly the moment a human reads the diff and
decides. Assume they said yes, because somebody wanted the feature and everything on the page is
correct.

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

## And this lab has none of it

There is no outbound tool here, and that is a decision rather than a gap somebody forgot to fill.
`CLAUDE.md` rule 7 forbids the general case — no SQL, shell, file or unrestricted HTTP tool — and
rule 8 covers what is left: a sensitive effect goes through propose, approve, execute, and the API
never performs it in the request path. A tool that sends is an irreversible effect with no rollback,
which puts it squarely inside rule 8.

Adding one to teach this challenge would have meant shipping the capability in every image of the
service the lab holds up as the well-built one. So the challenge teaches the audit instead, and the
absence is the thing you are asked to prove.

## Your task

1. Establish, from the surface rather than from this page, that no registered operation sends
   anything outside the system. Say what you read and what would have shown up if one did.
2. Be precise about what the absence is. *"This system cannot make an outbound connection"* is a
   claim you have not checked and it is not the one worth making. Write the narrower one.
3. One component here genuinely is built to reach outside. Find it. Say where it lives, what gates
   sit between the model and it, and which of those gates is a property of the code rather than a
   configuration setting.
4. Then write the useful half: the day somebody proposes `send_customer_email`, which of this lab's
   existing controls already covers the recipient, and what would have to be built for the content?

Question 4 is the one that survives contact with a real system, because most teams asking you to
review an agent already have the outbound tool.
