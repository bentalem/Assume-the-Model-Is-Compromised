# Where does an agent's tool list actually live?

It feels like a silly question. The tools are in the code — you can read them.

Then you go and count, and in this system there are three copies of that list, in three different
places, kept in step by three different mechanisms. One of those mechanisms is a person.

| | Copy | What it is | Kept in step by |
|---|---|---|---|
| 1 | **the code** | the modules that register each operation | it *is* the source of truth |
| 2 | **the exported document** | `openapi/supportpilot-actions.json` | a check on every commit |
| 3 | **the agent's registered actions** | whatever the agent platform holds | ? |

Two of the observations in the next stage show you copies 1 and 2. There is no observation for copy
3, and that is not an oversight in this challenge — it is the finding, arriving early.

## The check that exists, and what it says

Every commit runs a check that regenerates the document from the code and compares the two. When it
passes it prints:

```
OK: action document matches the code. Operations: add_internal_note, get_action_status, ...
```

That is a real control and it closes a real gap. Before it, a tool could change while the document
kept describing the old one, and nobody would notice until an agent called something that no longer
existed.

Read the sentence carefully though. **"Matches the code."** It compares copy 2 against copy 1. It is
a *comparison*, not a deployment — it does not push anything anywhere, and it makes no claim about
copy 3, because it has no way to see it.

## How copy 3 is made

Go and read the second source panel. The setup script does what it can automatically, and then
prints a list headed:

> *Left to you, because both need an Onyx admin login this script does not have:*
> *registering the action with passthrough auth (Admin Panel -> Actions).*

So the tool list reaches the agent because a person opens an admin panel and pastes a document into
a form. Once. At setup.

Nothing re-runs it. Nothing compares it afterwards. Nothing anywhere in this repository can even
read what ended up in that form.

## Why this is the normal case

It is tempting to call this a lab shortcut. It is not — it is how most agent platforms work today,
and it is worth being precise about why, because the reason is structural rather than lazy.

The tool list is **configuration in a different system**. Your repository does not own it. Your CI
cannot reach it. Your deployment pipeline does not touch it. It is in the same category as a DNS
record, a webhook URL or an IAM role somebody created by hand in a console — and it decides what
your agent can do.

> A control that lives in another team's product is still your control. It is just one you cannot
> test, cannot review in a diff, and will not notice drifting.

## The question to answer

Work out what happens on an ordinary Tuesday:

1. A tool is removed from the code because it was a bad idea.
2. The document is regenerated. The check passes — copies 1 and 2 agree.
3. The pull request is approved and merged.
4. Nobody opens the admin panel.

**What does the agent believe it can call on Wednesday?** And when it calls it, what does the API
do?

Answer that, then say what a reader of the passing check is entitled to conclude from it — and what
they are not.
