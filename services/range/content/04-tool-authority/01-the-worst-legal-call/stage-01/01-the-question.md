# A tool is not a function

This is the track that distinguishes the role, and the reason is that almost nothing here has an
equivalent in classical security. Identity, authorization, tenant isolation, audit — good engineers
already know those. This one they have not been asked about.

> **A tool is not a function. It is a grant of standing authority to something that is untrusted
> input and steerable by the text it reads.**

The same function already exists in the UI, and it is fine there. What changed is the caller:

| | The UI | The agent |
|---|---|---|
| Who decides to call | a person, on purpose | a model, influenced by what it read |
| How many times | once, per click | a hundred, per second |
| Who picks the arguments | a form with one field | the model, freely |
| Can it be steered by data | no | **yes — that is the whole threat** |

So when a team says *"it's the same API our web app uses"* — true, and beside the point. **The threat
model changed; the API did not.**

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

## Five parameter classes

Open the schema and scan for these:

| Class | Examples | Why |
|---|---|---|
| Identity | `user_id`, `role`, `approved_by` | the model decides who it is |
| **Interpreter** | `sql`, `query`, `path`, `url`, `template` | anything handed to an interpreter makes a specific tool generic |
| Scope | `limit`, `fields`, `include` | no new access, far more per call |
| Free text out | email body, comment, webhook payload | an exfiltration channel |
| Decision | `force`, `skip_validation` | the model writes its own justification |

And one rule that catches more than any other: **a parameter typed `object` with no schema is itself
the finding.** Not a request for clarification. It is a generic tool wearing a business name, which
is worse than one that looks generic, because nobody in the room becomes suspicious.

---

Now read the surface. Seven operations, from the document the agent is actually given.

Six of them are one shape. One is not.
