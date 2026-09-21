# The three questions

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
