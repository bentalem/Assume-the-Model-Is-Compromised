# What the audit found

Nothing. That is the answer, and it is only worth anything if you can say how you got it.

## Twelve parameters, three types

Every parameter on the surface, by the type the document declares:

| Operation | Parameters | Types |
|---|---|---|
| `get_order` | `order_number`, `include_items`, `include_shipment` | string, boolean, boolean |
| `search_customers` | `q`, `limit`, `cursor` | string, `?`, `?` |
| `get_customer` | `customer_ref` | string |
| `get_ticket` | `ticket_number`, `limit`, `cursor` | string, `?`, `?` |
| `add_internal_note` | `ticket_number` | string |
| `propose_refund` | none | the payload is the body |
| `get_action_status` | `action_id` | string |

Twelve parameters. Six strings, two booleans, four printed as `?`. No parameter on this surface is
typed `object`.

## The four question marks are not the finding

Worth pausing on, because a reviewer who reports them has reported the wrong thing and a reviewer
who ignores them without checking got lucky.

`limit` and `cursor` are declared as an `anyOf` — an integer with a minimum and maximum, or null;
a string with a `maxLength`, or null. An `anyOf` has no `type` at the top of its schema, and the
observation that draws this table reads `schema.type` with `?` as its fallback. So the `?` is the
listing saying *"the type is not where I looked"*, not the document saying *"there is no type"*.

> **A missing type in a listing and a missing schema in a document are different findings.** One is
> resolved by opening the document. The other is resolved by opening a code review.

This is the general shape of the skill. The listing narrows where to look. It does not answer.

## The two bodies are objects, and they are closed

`add_internal_note` and `propose_refund` both carry a body typed `object`. Both are bounded in the
document itself, which is the part that matters — a bound that only exists in the handler is a bound
the model was never told about, and a reviewer reading the published document cannot see.

| | `CreateNoteRequest` | `ProposeRefundRequest` |
|---|---|---|
| Declared properties | 2 | 5 |
| `additionalProperties` | `false` | `false` |
| Free text | `body`, `maxLength` 4000 | `note`, `maxLength` 500 |
| Closed value sets | `expected_ticket_status`, four values | `reason`, five values |
| Patterned | — | `order_number`, `^ORD-[0-9]{4,12}$` |

`additionalProperties: false` is the line that does the work, and it is generated rather than
written: `model_config = ConfigDict(extra="forbid")` on the Pydantic model is what emits it. The
source panel shows the refund body, where that config line sits directly above five fields that each
name a pattern, a length or a value set.

The second-order effect is worth taking from the other body. `notes.py` explains why `forbid` rather
than the default: a field the model invents comes back as a rejected request instead of being quietly
dropped, so the model does not go on believing it set something.

Thirteen named schemas in `components`, plus those two bodies inlined beside their operations.
Every one of them declares its properties and forbids the rest.

## The gap, which is the actual finding

`scripts/export_openapi.py` is the gate. The document is generated from the running routes and then
audited, and a failing audit means nothing is published. Read the two panels and list what it
enforces:

| Rule | About |
|---|---|
| Operation is on the approved list | the name |
| Parameter name is not `user_id`, `role`, `approved`, … | the name |
| String parameter has a pattern, `maxLength` or `enum` | the shape |
| Query parameter is not an array | the shape |
| Operation has a summary, and every success response has a schema | the shape |
| Schema does not set `additionalProperties: true` | the shape |
| Array property has `maxItems` | the shape |
| Property reference is not dangling | the shape |

Now put `run_saved_report` from Stage 01 through it. Read the first panel again before you do,
because the loop it shows walks `operation["parameters"]` — the path and query arguments. A request
body's properties never enter that loop. They are judged by the second panel, which walks
`components.schemas` and applies three rules.

- `parameters` is typed `object`. Not an array, so the `maxItems` rule does not apply.
- It carries no `$ref`, so the dangling-reference rule does not apply.
- The body does not set `additionalProperties: true`. It does not set it at all, and the rule tests
  for `is True`.
- It is not on the approved operation list — so it would be rejected, once, for being new.

That last line is the honest part of the answer and it is also the fragile part. The operation list
is the control that stops an unreviewed tool reaching the document, and it is a good one. But it
stops a tool *arriving*; it says nothing about a tool that is already approved growing a new
parameter next quarter. Add `parameters: {type: object}` to `propose_refund` and this audit publishes
it without a word.

> The check that would have caught it does not exist. What caught it is that somebody would have had
> to add the operation to a list, and a human would have read the diff.

That is a real control and it is worth crediting. It is also a review, not a test, and reviews are
the control that degrades when the team is busy.

## The rule applied to the thing that teaches it

The fourth panel is the Range's own SQL. The Range arms and restores controls on the lab, which means
it needs to turn row security off on a table and back on again — and a function
`set_row_security(table, enabled, forced)` would be the obvious way to write that.

It does not exist. There is one function per mutation with the table written into the body, and the
service's entire vocabulary is the list of functions it holds `EXECUTE` on. The comment at the top of
that migration says why in the terms of this track, which is the point: a repository that teaches
this finding and then ships one has taught nothing.

Check the claim in the direction that would embarrass it, not the direction that confirms it.

## Take it to a review

1. **Show me the published tool schema** — the document the model is given, not the API reference.
2. **Is any parameter or property typed `object`?** For each: what function reads it, and does that
   function index it or interpret it?
3. **Which parameters are free-form strings?** For each: what is it concatenated into before it
   reaches storage — a query, a path, a URL, a template, a prompt?
4. **What check runs over this document before it ships, and what does that check test?** Ask for
   the file. Then ask which of its rules are about parameter names and which are about parameter
   shapes.
5. **Who has to approve a new parameter on an existing tool?** If a new tool needs review and a new
   parameter does not, the review boundary is in the wrong place.

Question 5 is the one that generalises. Most tool-schema controls are built around *registration*,
because that is when the risk is visible. The change that widens a tool is an edit to something
already approved, and it arrives through the ordinary code path.
