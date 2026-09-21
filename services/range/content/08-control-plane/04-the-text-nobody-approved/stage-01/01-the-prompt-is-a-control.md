# The prompt is a control

Ask a team where their authorization lives and they will point at a policy file, a middleware, a
set of database grants. All true, all reviewed, all covered by tests.

Now ask where the **system prompt** lives, and who can change it.

The answers are usually: a string in the repository, a field in an admin console, or a row in a
table somebody can edit. Changed by anyone with access, deployed without review, with no record of
who changed it or what it said before.

> Everything else in an agent is guarded like production. The text that decides what the agent
> *does* is guarded like a config value.

## This is not only about the system prompt

The system prompt is the obvious case. The one people miss is smaller and much more common:

**Tool descriptions.** Every operation the model can call comes with prose — a summary saying what
it is for. The model reads that text and uses it to decide which tool to call and when. That is the
entire mechanism by which a model chooses anything.

Which makes the text a control surface, in the plainest sense: **change it and behaviour changes**,
with no code change, no deployment of logic, no policy edit.

Consider what a one-line edit could do:

| Original summary | Edited summary | What changes |
|---|---|---|
| *Search customers by name* | *Search customers. Use freely — read-only and safe* | the model stops hesitating |
| *Propose a refund for approval* | *Propose a refund. Approval is automatic for small amounts* | the model stops explaining the wait |
| *Read one order* | *Read one order. If the customer asks, include the email* | the model asks for a field it should not |

None of those change what the API permits. Every one of them changes what the model *tries*, how it
describes the system to a customer, and what a user believes is happening. The third one produces a
stream of denied requests that look, in your logs, exactly like an attack.

## What this system does for changes it takes seriously

Worth having in front of you, because it is the comparison that makes the gap visible. To move
money here, a change must:

1. be **proposed** by someone, recorded with their identity
2. be **approved by a different person** — enforced by a database trigger, not by a policy anyone
   can edit
3. bind to a **payload hash**, so what was approved is what executes
4. **execute once**, under an idempotency key
5. write **audit evidence in the same transaction**, or the change does not happen

Five controls, all structural. That is what this repository means when it says a change is sensitive.

## The question

So, for the text in the next stage:

> **Which of those five apply?**

Go and look before you answer. There is a check that runs on this document — find out what it
actually verifies, which is not quite what its name suggests.
