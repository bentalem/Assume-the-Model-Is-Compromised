# Forgetting means finding every copy

One remembered fact may exist in more than one place:

- Its original row in `mem.records`.
- A point containing its vector and text in a per-organisation Qdrant collection.
- A second point in the lab's shared collection.
- A summary derived from the original.
- Vector copies of that summary.

There may also be older copies in transcripts, context logs and backups. Our `forget` tool does **not** erase those historical records.

## The full memory delete path

The service starts with the memory the user owns. It follows `derived_from` to find summaries and later derived records. It marks those records as forgotten in PostgreSQL and places vector deletions in the outbox. After commit, it removes the Qdrant copies.

The database's row-level security still limits whose records can be forgotten.

## Your task

Save and confirm a memory. Make a summary from it. Then forget it with complete deletion enabled and check every memory copy the observation can see.

Repeat with primary-only forgetting enabled. The original disappears, but derived records and vector copies can remain.

Turning the safe setting back on does not fix copies left behind. The Range's restore also runs the repair step and compares both stores.
