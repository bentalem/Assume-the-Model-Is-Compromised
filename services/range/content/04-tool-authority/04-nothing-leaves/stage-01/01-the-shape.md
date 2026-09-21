# The shape

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
