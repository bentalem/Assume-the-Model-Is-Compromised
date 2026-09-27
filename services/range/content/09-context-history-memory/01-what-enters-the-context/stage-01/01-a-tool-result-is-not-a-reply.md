# A tool result can become future context

The tool returns some text. The runtime saves it in conversation history. On the next turn, context assembly may send that text to the model again.

```text
User asks about an export
  -> tool returns an export log
  -> runtime saves the tool result in mem.turns
  -> context assembly loads recent history
  -> model reads the saved tool result again
```

If the log contained a credential, saving the tool result makes the credential available on later turns. The same problem can happen when the model copies it into a long-term memory.

## Where this lab stops it

When the runtime saves a turn, `history.py` calls the secret filter **before** writing it to PostgreSQL. Recognised credential-shaped values are replaced. Long-term memory takes a stricter path: `remember` refuses a recognised credential rather than saving a blank memory.

The filter only detects formats it knows. It will not find every secret. Tool permissions and limits on what the model can send remain necessary.

## Your task

First, observe the tool result with the filter enabled. Then turn the filter off and run the same observation. Look at the context block the service saved. The model did not have to steal anything; the runtime saved the tool output and brought it back.

Restoring the filter protects **new writes**. It does not remove the bad turn saved while the filter was off.
