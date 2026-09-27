# What an incomplete forget left behind

## What your result proves

With complete forgetting, the source record and its derived records were marked forgotten, and the vector copies were removed. With primary-only forgetting, the source could disappear while a summary remained live and searchable.

The important result is not just that a row was deleted. It is **which copies could still reach a later context or a direct store reader**.

## How complete forgetting works

The service finds the record under the owner's database permissions. It follows `derived_from` links to find summaries and any records made from those summaries.

It uses the narrow `mem.forget_records` database function to mark the selected records as forgotten. In the same transaction, it creates outbox jobs for their vector copies. After commit, the service applies the deletions in both Qdrant layouts.

PostgreSQL is the source of truth. Qdrant follows it after the database transaction; the stores do not share one atomic commit.

With the unsafe `forget.scope=primary` setting, the service skips the derived records and their vector cleanup. A summary may still pass the confirmed-memory check even though its original was forgotten.

## Why restore runs a repair job

Putting the setting back to complete forgetting protects the **next** delete. It does not remove old summaries or vectors left behind by an earlier incomplete delete.

The Range therefore runs the memory initialization repair after restoring the setting. The repair finds live records derived from forgotten sources and stale vectors that should no longer exist.

The reconciliation check compares PostgreSQL with both Qdrant layouts. An empty outbox does not, on its own, prove that every copy is gone.

## What this forget does not promise

Old conversation transcripts, old context logs and backups may contain the same fact. This memory operation does not remove them. A production deletion policy must define how those historical copies are handled.

## Take it to a review

- Where is a memory copied, summarized or cached after its first write?
- Can you follow the full chain of derived records when the user asks to forget?
- Which checks prove that vector copies were actually removed?
- What is the retention and deletion policy for transcripts, context logs and backups?
