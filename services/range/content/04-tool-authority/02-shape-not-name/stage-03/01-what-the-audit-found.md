# What the audit found

## What your result proves

Nothing. That is the answer, and it is only worth anything if you can say how you got it.

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

Twelve parameters. Six strings, two booleans, four printed as `?`. No parameter on this surface is typed `object`.

**The four question marks are not the finding.** `limit` and `cursor` are declared as an `anyOf` — an integer with a minimum and maximum, or null; a string with a `maxLength`, or null. An `anyOf` has no `type` at the top of its schema, and the observation that draws this table reads `schema.type` with `?` as its fallback. So the `?` is the listing saying *"the type is not where I looked"*, not the document saying *"there is no type"*.

> **A missing type in a listing and a missing schema in a document are different findings.** One is resolved by opening the document. The other is resolved by opening a code review.

**The two bodies are objects, and they are closed.** `add_internal_note` and `propose_refund` both carry a body typed `object`, and both are bounded in the document itself — which matters, because a bound that only exists in the handler is one the model was never told about.

| | `CreateNoteRequest` | `ProposeRefundRequest` |
|---|---|---|
| Declared properties | 2 | 5 |
| `additionalProperties` | `false` | `false` |
| Free text | `body`, `maxLength` 4000 | `note`, `maxLength` 500 |
| Closed value sets | `expected_ticket_status`, four values | `reason`, five values |
| Patterned | — | `order_number`, `^ORD-[0-9]{4,12}$` |

## Where the control lives

In two places, and they are different kinds of thing.

**The models.** `additionalProperties: false` is generated rather than written: `model_config = ConfigDict(extra="forbid")` on each Pydantic model emits it. The first source panel shows the refund body, where that line sits directly above five fields that each name a pattern, a length or a value set. `notes.py` explains why `forbid` rather than the default: a field the model invents comes back as a rejected request instead of being quietly dropped, so the model does not go on believing it set something.

**The gate.** `scripts/export_openapi.py` generates the document from the running routes and audits it; a failing audit writes nothing.

| Rule | About |
|---|---|
| Operation is on the approved list | the name |
| No parameter is exposed as a header | where it is |
| Parameter name is not `user_id`, `role`, `approved`, … | the name |
| String parameter has a pattern, `maxLength` or `enum` | the shape |
| Query parameter is not an array | the shape |
| Operation has a summary, and every success response has a schema | the shape |
| Schema does not set `additionalProperties: true` | the shape |
| Array property has `maxItems`; property reference is not dangling | the shape |

And the rule applied to the thing that teaches it: the last panel is the Range's own SQL. The Range needs to turn row security off on a table and back on — and a function `set_row_security(table, enabled, forced)` would be the obvious way to write that. It does not exist. There is one function per mutation, with the table written into the body. A repository that teaches this finding and then ships one has taught nothing.

## What this check does not cover

Put `run_saved_report` from Stage 01 through the gate. The parameter loop (the second panel) walks `operation["parameters"]` — the path and query arguments. A request body's properties never enter that loop. They are judged by the third panel, which walks the schemas and applies three rules:

- `parameters` is typed `object`. Not an array, so the `maxItems` rule does not apply.
- It carries no `$ref`, so the dangling-reference rule does not apply.
- The body does not set `additionalProperties: true`. It does not set it at all, and the rule tests for `is True`.
- It is not on the approved operation list — so it would be rejected, once, for being new.

That last line is the honest part of the answer and the fragile part. The approved list stops a tool *arriving*; it says nothing about an approved tool growing a new parameter next quarter. Add `parameters: {type: object}` to `propose_refund` and this audit publishes it without a word.

> The check that would have caught it does not exist. What caught it is that somebody would have had to add the operation to a list, and a human would have read the diff.

That is a real control and it is worth crediting. It is also a review, not a test — and nothing runs even the test unless somebody runs the script. (The memory service's document, from track 9, goes through a stricter version of the same gate: its request bodies must forbid extra properties and may not carry fields the server decides. Neither gate checks for a property typed `object` with no properties of its own.)

## Take it to a review

1. **Show me the published tool schema** — the document the model is given, not the API reference.
2. **Is any parameter or property typed `object`?** For each: what function reads it, and does that function index it or interpret it?
3. **Which parameters are free-form strings?** For each: what is it concatenated into before it reaches storage — a query, a path, a URL, a template, a prompt?
4. **What check runs over this document before it ships, and when does it run?** Ask for the file. Then ask which of its rules are about names and which are about shapes.
5. **Who has to approve a new parameter on an existing tool?** If a new tool needs review and a new parameter does not, the review boundary is in the wrong place.

Question 5 is the one that generalises. Most tool-schema controls are built around *registration*, because that is when the risk is visible. The change that widens a tool is an edit to something already approved, and it arrives through the ordinary code path.
