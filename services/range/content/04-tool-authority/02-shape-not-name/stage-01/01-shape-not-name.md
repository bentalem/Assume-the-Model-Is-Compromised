# Shape, not name

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

## The three questions to ask of it

You do not have to guess. An object parameter is answerable in about ten minutes:

| Ask | Because |
|---|---|
| What reads it? | The schema is not the contract. The function that consumes it is |
| Does the reader interpret it, or index it? | `params["team"]` is a lookup. `query.format_map(params)` is a language |
| What set of operations can it select? | That set, not the operation id, is the real tool list |

The third answer is the finding, and it is usually much larger than the name suggests. If
`parameters` reaches a report definition that builds SQL from it, the registered tool list has one
entry and the actual tool list has however many predicates that builder accepts.

## The ladder

Rate every argument on what the caller gets to choose. This is the same ladder 4.1 walked for reach,
one rung further up.

| The argument | What the caller selects | Reviewed? |
|---|---|---|
| `order_number`, pattern `^ORD-[0-9]{4,12}$` | one operand, named in advance | yes, at design time |
| `q`, free text | a set of operands | yes — and 4.1 is about how large that set is |
| `filters: object` | the predicate | no. You reviewed the noun, not the sentence |
| `parameters: object` | whatever the handler dispatches on | no. You did not review anything |

The move from row two to row three is the one this challenge is about. It is not a widening of
scope. It is a change of kind: from a tool that answers a question to a tool that accepts questions.

## Why a name-based check cannot find it

This repository audits its own action document before publishing it, and the audit has a list of
parameter names it refuses — `user_id`, `organization_id`, `role`, `approved` and the rest. That
list exists for rule 1, and it works, because the identity fields a model must never supply have
well-known names.

Genericity has no well-known name. There is no word you can ban. `parameters`, `options`, `context`,
`metadata`, `extra`, `payload`, `config`, `args` — all ordinary, all innocent nine times out of ten.
The only thing that distinguishes the tenth is the shape, which means the check has to be about the
shape, which means somebody has to have written that check.

## Your task

Read the whole surface, not the interesting part of it. Seven operations; count every parameter and
every request body field, and for each one write down whether it declares what it accepts.

Then answer three things:

1. Is any parameter or body property typed `object` with no declared properties? Say how you
   established it, rather than that you looked.
2. The two POST operations do carry a body typed `object`. What makes those bodies bounded, in the
   document rather than in the code?
3. Go to `scripts/export_openapi.py`. It is the gate the document passes through. Which of its rules
   would have rejected the `run_saved_report` above, and which would have let it through?

Question 3 is the one worth your time. A surface that is clean today is a fact about today. A check
that would catch it is a fact about next quarter.
