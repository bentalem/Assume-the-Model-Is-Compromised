# Why the secret survived

## What your result proves

With the filter enabled, the tool result was saved with the recognised secret removed. After you disabled the filter, the new tool result was saved with that value still present. The next context included the unsafe turn because it was already part of the user's history.

The important result is **where the secret entered the system**. The problem started when the runtime saved the tool result, before the model received its next context. No new permission or special model behaviour was needed.

## Where the control lives

The write route in `history.py` checks `write.secret_filter` inside the transaction that saves a turn. When it is enabled, `secrets_filter.py` replaces recognised credential patterns before the database insert.

`context.py` later reads the stored turn. It does not apply the same filter again on the way out. That is why a value written while the filter was disabled can reappear in a later context.

Long-term memory takes a different path: its write route refuses a recognised secret. A redacted history turn still records that something happened; a redacted long-term fact would usually have no value.

## What restoring fixes

Restoring the filter protects **future writes**. It does not change an unsafe turn that was already stored. That turn may also have appeared in one or more saved context logs. Repair needs a separate decision about those old copies.

Pattern matching has limits. A secret in an unexpected format may pass the filter even when it is enabled. The API should still return only fields the user needs, and the agent's tools should not provide an open route for sending data elsewhere.

## Take it to a review

- Which tools can return credentials, and why are those fields available?
- Is the secret filter applied before every history write, including tool results?
- Can you find the sessions and context logs created while the filter was disabled?
- What is the plan for cleaning up old copies without destroying audit evidence?
