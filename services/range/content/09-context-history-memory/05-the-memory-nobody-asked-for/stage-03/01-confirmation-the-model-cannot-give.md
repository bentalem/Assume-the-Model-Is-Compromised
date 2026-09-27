# How an unconfirmed fact became trusted memory

## What your result proves

With the normal setting, the model could save a new fact but could not make it appear in Alice's next context. The record existed as `unconfirmed` and waited for her decision.

With auto-confirmation enabled, the same model-facing tool created a **confirmed** record. The next context could include it without Alice's approval. The unsafe behaviour came from a setting on the memory write path, not from a new model permission.

## Where confirmation is controlled

The model's `remember` tool accepts only the memory text. The service decides the owner and source channel from the authenticated request. The PostgreSQL insert policy checks that a model-written record is not born confirmed unless `write.auto_confirm` permits it.

Manual confirmation uses a different route. It is not part of the model's action document. The runtime calls it on behalf of the owner after they agree to save the memory.

Only confirmed records are selected for context. The status check is what stops an injected note from becoming persistent context immediately.

## What restore does

Disabling auto-confirmation stops new model-written records from being confirmed automatically. It does not change the status of records created while the setting was unsafe.

The Range's restore performs that second step: it returns auto-confirmed memories to `unconfirmed` and records the change. Alice can still review and confirm a record herself. Old context logs may contain the unsafe text if it was already used before restore.

The same principle applies to any memory system: fixing the setting is not enough if bad facts were accepted while the setting was open.

## Take it to a review

- Can a model-facing tool choose the memory owner or approval status?
- What evidence shows whether a memory was confirmed by a user or automatically?
- Can you find and review everything auto-confirmed during an unsafe period?
- Can a later summary preserve a poisoned memory after its original record is forgotten?
