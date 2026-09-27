# A confirmation the model cannot give

The decision chain for the model's write:

1. **`remember` is called** — the model-facing tool, in the memory action document. The request body has one field, `content`. It cannot say who wrote it, what channel it came from, or whether it is confirmed; the action-document gate refuses any of those in a body.
2. **The channel is fixed by the route**: this is the model's endpoint, so the record is `agent`.
3. **Status is `unconfirmed`** — unless `write.auto_confirm` is on, in which case it is born `confirmed` with `confirmed_via = 'auto'`. The insert policy in the store checks the same setting, so the service alone cannot decide it.
4. **Context selects confirmed memories only.** Unconfirmed, the note exists and is never used.
5. **Confirmation** is `POST /v1/memories/{id}/confirm` — a runtime route, absent from the action document. The model has no tool that reaches it. That is what makes it a person's decision.

## What restoring the setting does

Closing auto-confirm stops new memories being born confirmed. On its own it does nothing about the
ones that already were — they would stay in alice's context indefinitely. So the Range's restore does
a second thing: every memory whose `confirmed_via` is `auto` goes back to `unconfirmed`, to wait for
its owner, with an audit event each. Nothing is deleted; alice can still confirm what she wants.

That second step is the part real incidents usually lack. Fixing the setting is the patch. Finding
what came through while it was open is the response.
