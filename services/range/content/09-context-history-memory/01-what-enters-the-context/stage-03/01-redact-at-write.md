# Redact at write, and what restoring does not undo

The decision chain for one tool turn:

1. **The runtime appends the turn** — `POST /v1/sessions/{id}/turns`, as the user whose session it is. Identity from the token; the session must be theirs, which row-level security checks.
2. **The service reads `write.secret_filter`** from memory-db, in the same transaction.
3. **If a secret is found, the content is replaced before the insert.** The audit event records `redacted_secret`; the stored turn never contains the value.
4. **Context assembly replays the stored turn.** It has nothing to filter, because it was never given anything.

Notice what the code does *not* do: it does not scan the context block on the way out. A filter at
read time would have to be right on every path that reads — and memory has several.

## Turns and records are treated differently, on purpose

| | With a secret in it | Why |
|---|---|---|
| History turn | stored, redacted | the conversation has to be recorded; a turn that cannot be written breaks the runtime |
| Long-term memory | **refused** (`secret_refused`) | there is no legitimate reason to remember a credential, and a redacted stub is noise |

## A floor, not a guarantee

The filter recognises secrets by shape — the same patterns the service's log redactor uses, so there
is one definition rather than two that drift. It catches credentials that look like credentials: an
AWS key, a bearer token or a JWT, a connection string with a password in it, a value assigned
to a name like `api_key`. It does not catch a password in a sentence, a customer's
card number written out in words, or anything a tool returns in a format nobody wrote a pattern for.

So it is a floor. The controls that do not depend on recognising the secret are the ones the rest of
this lab builds: an agent whose tools return only the fields a caller may see (track 3), and that has
nowhere to send what it reads (track 4).

## What restoring the filter does not undo

Re-arm the filter and the next tool result is redacted again. The one you stored while it was off
**is still in alice's history** — turns are append-only, by design, because a history that can be
rewritten is not evidence of anything.

That is the recovery question every real incident of this shape ends with: not "is the hole
closed?" but "what came through it, where is it now, and who has read it since?". In this lab the
answer is in `mem.context_log`: every block that contained it, and whose it was.
