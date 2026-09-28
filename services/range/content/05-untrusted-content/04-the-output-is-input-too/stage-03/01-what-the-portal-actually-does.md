# What the portal actually does

## What your result proves

**The approval portal escapes its output correctly.** There is no template engine and therefore no autoescaping to rely on: it is a hand-written f-string, and every value that goes into it is wrapped in `html.escape` first.

| Where | What it escapes |
|---|---|
| `main.py:127` | `e = html.escape`, the alias used for the rest of the function |
| `main.py:131` | the canonical payload, before it reaches the `pre` block |
| `main.py:139`–`147` | all ten values in the definition list |
| `main.py:154` | the sha256 digest |
| `main.py:163`, `168` | the action id, inside a single-quoted attribute |
| `main.py:165`, `170` | the payload hash, inside a single-quoted attribute |
| `main.py:65` | the page title, in the wrapper |
| `main.py:207`, `220` | the decision word and the failure reason on the result page |

Sixteen applications in the review handler alone, and none missing.

## Where the control lives

There are two controls, and the order they are built in matters.

**The first control is the schema of what can reach the page.** `propose_refund` accepts five fields and freezes six keys, and the two lists do not match:

| Field the caller sends | What happens to it |
|---|---|
| `order_number` | used to look up the order; the payload stores the number from the loaded row, not the string sent |
| `amount` | parsed as a `Decimal`, must be positive, at most two decimal places, re-formatted |
| `currency` | three alphabetic characters, uppercased |
| `reason` | a five-value enum — `damaged_on_arrival`, `not_delivered`, `wrong_item`, `duplicate_charge`, `other` |
| `note` | accepted, up to 500 characters, and then never read — `payload.note` appears nowhere in the API or the worker |

`organization_id` and `action_type` are added server-side. So **no free text a caller chooses reaches the approver's screen.** Not one of the six payload keys can hold an arbitrary string.

**The second control is the escaping**, and two details make it correct rather than lucky:

- **Single-quoted attributes.** The forms are written with single quotes, which is where a lot of hand-rolled escaping fails. Python's `html.escape` takes `quote=True` by default, which escapes both quote characters (`"` to `&quot;`, `'` to `&#x27;`), so `action='/actions/{e(action_id)}/decide'` cannot be closed early. Had the code called `html.escape(value, quote=False)` — which the Range's own Markdown renderer does at `markdown.py:32`, correctly, because it is escaping text and not attributes — the attributes here would be breakable.
- **The wrapper trusts its body, and is allowed to.** `_page` escapes `title` and interpolates `body` raw. That looks like the bug until you check where `body` comes from: it is built a few lines above, by the same module, from values that were each escaped individually. The rule is escape at the point of interpolation, once — and it is followed consistently.

The escaping is a second layer over a surface that already has nothing to inject with — the right order to have built it in, and the wrong order to have reviewed it in.

## What this check does not cover

**Escaping does not make the screen tell the truth.** It stops markup; it does not stop a wrong amount being displayed faithfully. An approver shown one amount who signs a hash for another has done the review perfectly and approved the wrong thing — which is why the portal shows the canonical payload beside its hash, and why the worker recomputes that hash. Challenge 6.1.

**`note` promises a record and keeps none.** It is declared in the request model, published in the action document the model reads, and never referenced again. A caller that writes a careful explanatory note gets a `201` and the note is discarded. Nothing is exposed by that; it tells the model it recorded something it did not.

**A control with no test is a control somebody is trusting.** For a long time `services/approval-portal/tests/` was empty. Read what the test file now asserts, because the obvious test is the less useful one: checking that `<script>` comes back escaped would pass even if somebody changed `html.escape(value)` to `html.escape(value, quote=False)` — and several values sit inside single-quoted attributes, which that change would make injectable. So the quotes are asserted separately, and the library's default is asserted too.

## Take it to a review

In a system that is not this one, you are looking for the point of interpolation and what wraps the value there. Four shapes, in descending order of how much reading they need:

```
f"<td>{value}</td>"                    no wrapper at all - assume it is exploitable
"<td>" + escape(value) + "</td>"       check every branch; one missed call is the bug
Template(autoescape=True)              check for |safe, |raw, mark_safe, dangerouslySetInnerHTML
element.textContent = value            cannot produce markup; this is the one to prefer
```

And the question that precedes all four: could a model have chosen that string, and how long is it allowed to be?

1. List every place an agent's output is displayed to a human or stored where a human will later see it. Approval screens, ticket replies, dashboards, Slack messages, PDF summaries, email.
2. For each surface, name the rendering call and read it. Not the framework — the line. A template engine with autoescaping is a good answer only once you have grepped for the escape hatch.
3. Before that, find the schema of what the model may put there. A closed enum and a validated decimal are a stronger answer than any amount of escaping, and they are cheaper to keep true.
4. Ask which fields the model may send that are free text, and follow each one to where it is stored and read back. A field that is accepted and dropped is worth reporting on its own.
5. Check whether the escaping is tested. "There is no test" is a finding you can write without waiting for the regression.
6. Rank the surface by what a wrong pixel costs. A rendered script in a marketing page and a wrong amount on an approval screen are not the same finding, and the second one does not need a script to do damage.
