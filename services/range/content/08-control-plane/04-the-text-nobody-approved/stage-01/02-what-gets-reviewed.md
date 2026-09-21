# What gets reviewed

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
