# What makes a tool generic

Challenge 4.1 ended on a rule and did not stop to explain it:

> **A parameter typed `object` with no schema is itself the finding.** Not a request for
> clarification.

This challenge is that one rule, done properly, because it is the finding most often missed in a
real review and the reason is not technical. A tool called `execute_sql` gets an argument in the
room. A tool called `run_saved_report` does not, and it can be the same tool.

## What makes a tool generic

Not the verb. Not the name. One property:

> **A tool is generic when the caller's argument selects the operation, rather than selecting the
> operand the operation runs on.**

`get_order(order_number)` lets the caller choose *which order*. The operation is fixed and was
reviewed. A parameter that reaches an interpreter — SQL, a shell, a path, a URL, a template — lets
the caller choose *what happens*, and nothing about that was reviewed, because it had not been
written yet when the review took place.

An object with no declared properties is the same thing without the giveaway word. It does not say
`sql`. It says nothing at all, and whatever the handler does with its contents is the actual API.

## What this looks like in a document

Here is a tool you would let through. It is not from this lab — nothing in this repository has this
shape, and the rest of the challenge is establishing that — so read it as a specimen.

```
  post:
    operationId: run_saved_report
    summary: Run one of the organisation's saved reports
    requestBody:
      content:
        application/json:
          schema:
            type: object
            required: [report]
            properties:
              report:
                type: string
                enum: [open_tickets, refunds_this_month, customers_by_team]
              parameters:
                type: object
```

Everything a reviewer checks is right. The operation is on the approved list. It has a summary. The
report name is an enum of three values, so the model cannot ask for a fourth. The route is
authenticated, the tenant is server-derived, the response is bounded.

And the last two lines are an undocumented API of unknown size, reachable through a reviewed one.

The honest reading of `parameters: {type: object}` is *"whatever the handler does with a dictionary
it was handed"*. That is not a schema. It is a promise to read the handler, made by somebody who
has not read the handler.
