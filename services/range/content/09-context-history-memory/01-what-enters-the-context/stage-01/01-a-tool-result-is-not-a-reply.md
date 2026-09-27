# A tool result is not a reply

A model is stateless. Every turn, the agent runtime rebuilds the whole conversation and sends it
again — the system prompt, the rules, the memories it selected, and the history of the session so
far. That rebuilt text is the **context block**, and it is the only thing the model ever reads.

History is not only what the user typed. A tool call's result is written into history too, as its
own turn, so that the next turn knows what the tool said:

```
user       "what happened with last night's export job?"
tool       get_deploy_log → "... authenticated with <credential> at 02:14 ..."
assistant  "the export ran at 02:14 and finished without errors"
```

Nobody reads that tool turn before it is stored. Nobody reads it before it is replayed. The next
question in the same session sends it to the model again, and so does the one after that.

## Three places a secret could be stopped

| Where | What it would take | What it misses |
|---|---|---|
| **At write** — when the runtime stores the turn | a filter on the one path into the store | nothing downstream, because nothing downstream ever has it |
| At read — when context is assembled | a filter on every path out | any path out that was forgotten: search, export, a transcript view |
| In the model's answer | the model noticing, every time | everything, the first time it does not |

Only the first one is a control. The second is a promise about every reader that will ever exist,
and the third is not in your code at all.

This service redacts at write. A history turn carrying something credential-shaped is stored with
the value replaced; a long-term memory carrying one is refused outright.
