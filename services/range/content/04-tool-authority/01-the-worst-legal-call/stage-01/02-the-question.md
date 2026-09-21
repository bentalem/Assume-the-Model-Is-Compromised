# The question

## The question

For every tool, one question, and it is worth memorising exactly:

> **What is the worst thing one legal call can do, for your most privileged user, when an attacker
> chooses every argument?**

Every clause kills an excuse:

- **"legal"** — this is not a bug hunt. The finding is the tool *doing exactly what it was built to
  do*.
- **"one"** — isolate the tool before looking at chains.
- **"most privileged user"** — ends "our users can't do that", which stops being true the moment a
  manager opens a chat window.
- **"attacker chooses every argument"** — ends "the model wouldn't ask for that".

Answer in **one concrete sentence**, never a severity rating. *"This tool is risky"* is what the room
already thinks and it changes nothing. *"The model chooses both the recipient and the body, so
customer A's records can be emailed to customer B from the company's own address"* stops a meeting.

## Three dimensions to rate before reading any code

**Reach.** How many objects can one call touch?

```
get_order(order_number)   one object, named in advance      narrow
search_customers(q)       a set the caller composes          wide
list_customers()          everything                         everything
```

The move from **identifier** to **query** is the most important transition in this track. An
id-taking tool reaches only what is already known. A query-taking tool lets the caller choose the
set — which makes it a bulk-extraction primitive wearing the name of a lookup.

**Effect.** read → write → irreversible write → **effect outside the system**. The last is worst:
once something has left, there is no rollback for email.

**Rate.** What do a thousand calls compose into? This is the dimension nobody rates, and it is the
one an attacker uses.

> **Permission is evaluated per call. Damage accumulates across calls.** Your findings live in that
> gap.
