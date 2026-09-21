# What the portal actually does

Here is the answer, so that you can check it against what you found rather than guess at what this
page wants you to say.

**The approval portal escapes its output correctly.** There is no template engine and therefore no
autoescaping to rely on: it is a hand-written f-string, and every single value that goes into it is
wrapped in `html.escape` first.

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

## The two details that make it correct rather than lucky

**Single-quoted attributes.** The forms are written with single quotes, which is where a lot of
hand-rolled escaping fails. Python's `html.escape` takes `quote=True` by default, and that flag
escapes both quote characters:

```
"  ->  &quot;
'  ->  &#x27;
```

So `action='/actions/{e(action_id)}/decide'` cannot be closed early. Had the code called
`html.escape(value, quote=False)` — which is what the Range's own Markdown renderer does at
`markdown.py:32`, correctly, because it is escaping text and not attributes — the single-quoted
attributes here would be breakable.

**The wrapper trusts its body, and is allowed to.** `_page` escapes `title` and interpolates `body`
raw. That looks like the bug until you check where `body` comes from: it is built a few lines above,
by the same module, from values that were each escaped individually. Escaping it again would print
tags to the screen. The rule being followed is escape at the point of interpolation, once — and it
is followed consistently.

## The first question, answered

Now the part that matters more.

`propose_refund` accepts five fields and freezes six keys, and the two lists do not match:

| Field the caller sends | What happens to it |
|---|---|
| `order_number` | used to look up the order; the payload stores the number from the loaded row, not the string sent |
| `amount` | parsed as a `Decimal`, must be positive, at most two decimal places, re-formatted |
| `currency` | three alphabetic characters, uppercased |
| `reason` | a five-value enum — `damaged_on_arrival`, `not_delivered`, `wrong_item`, `duplicate_charge`, `other` |
| `note` | accepted, up to 500 characters, and then never read — `payload.note` appears nowhere in the API or the worker |

`organization_id` and `action_type` are added server-side.

So **no free text a caller chooses reaches the approver's screen.** Not one of the six payload keys
can hold an arbitrary string. The escaping at `main.py:127` is a second layer over a surface that
already has nothing to inject with, which is the right order to have built it in and the wrong order
to have reviewed it in.

And `note` is worth stating on its own, because it is a real and checkable oddity: it is declared in
the request model at `actions.py:64`, it is published in the action document the model reads, and it
is never referenced again. A caller that writes a careful explanatory note gets a `201` and the note
is discarded. Nothing is exposed by that. It is a field that promises a record and keeps none.

## What is missing

The escaping here is correct and has always been correct. For a long time nothing in this
repository would have noticed if it stopped being — `services/approval-portal/tests/` was empty.

That is how this gap is normally found. Every other capability in the lab ships with a positive, a
negative and a cross-tenant test; the one service that renders values into a human's browser had
none, in a repository that argues loudly for exactly that. A control with no test is a control
somebody is trusting.

Read what the new file asserts, because the obvious test is the less useful one. Checking that
`<script>` comes back escaped would pass even if somebody changed `html.escape(value)` to
`html.escape(value, quote=False)` — and several values on that page sit inside single-quoted HTML
attributes, which that change would make injectable. So the quotes are asserted separately, and the
library's default is asserted too, because the page depends on it and nothing else would fail if it
moved.

That is the finding to write up from this challenge, and it is a better one than an escaping bug
would have been, because it is about the thing that keeps being true rather than the thing that is
true now.

## The line you would check elsewhere

In a system that is not this one, you are looking for the point of interpolation and what wraps the
value there. Four shapes, in descending order of how much reading they need:

```
f"<td>{value}</td>"                    no wrapper at all - assume it is exploitable
"<td>" + escape(value) + "</td>"       check every branch; one missed call is the bug
Template(autoescape=True)              check for |safe, |raw, mark_safe, dangerouslySetInnerHTML
element.textContent = value            cannot produce markup; this is the one to prefer
```

And the question that precedes all four: could a model have chosen that string, and how long is it
allowed to be?

## Take it to a review

1. List every place an agent's output is displayed to a human or stored where a human will later
   see it. Approval screens, ticket replies, dashboards, Slack messages, PDF summaries, email.
2. For each surface, name the rendering call and read it. Not the framework — the line. A template
   engine with autoescaping is a good answer only once you have grepped for the escape hatch.
3. Before that, find the schema of what the model may put there. A closed enum and a validated
   decimal are a stronger answer than any amount of escaping, and they are cheaper to keep true.
4. Ask which fields the model may send that are free text, and follow each one to where it is
   stored and read back. A field that is accepted and dropped is worth reporting on its own: it
   tells the model it recorded something it did not.
5. Check whether the escaping is tested. An untested control is a control that works until somebody
   refactors, and "there is no test" is a finding you can write without waiting for the regression.
6. Rank the surface by what a wrong pixel costs. A rendered script in a marketing page and a wrong
   amount on an approval screen are not the same finding, and the second one does not need a script
   to do damage.
