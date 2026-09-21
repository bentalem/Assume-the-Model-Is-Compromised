# Where authority leaks

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
