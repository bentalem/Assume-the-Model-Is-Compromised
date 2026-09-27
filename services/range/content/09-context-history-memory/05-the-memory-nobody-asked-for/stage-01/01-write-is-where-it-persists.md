# A saved memory can carry an instruction into a new conversation

The model reads an internal ticket note. The note tells it to remember a false policy about refunds. If the model calls `remember`, the note can become a saved record that may come back in later chats.

That is different from ordinary conversation history: the original chat may end, but long-term memory remains.

## The safe path

A model-written record starts as `unconfirmed`. The model cannot set the status in its request and cannot call the route that confirms it. Until the user confirms it, context assembly leaves it out.

When the auto-confirm setting is on, model-written memories become confirmed at once. The model has not gained a new tool; the same write now has a different result.

## Your task

Ask the lab's runtime to save the ticket note with auto-confirm off, then on. Look at the record status, how it was confirmed and whether it appears in the next context.

Turning auto-confirm off again stops **new** memories from becoming active. The Range's restore also moves previously auto-confirmed memories back to waiting for confirmation.

A stored fact should not become trusted just because the model decided to save it.
