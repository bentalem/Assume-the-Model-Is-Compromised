# A successful forget must reach all memory copies

A full forget finds the user's live record under row-level security. It follows `derived_from` to find all its summaries and later derived records.

The service calls a narrow database function to mark these rows forgotten. It writes vector-delete jobs to the outbox in the same transaction, then removes both Qdrant layouts after commit.

That function matters because a normal update to `deleted_at` conflicts with the table's policy that hides forgotten rows. The narrow function keeps ownership checks in the store.

When `forget.scope` is set to `primary`, only the original row is forgotten. A summary can still enter context, and vector copies can still be read directly.

The Range's restore runs a repair step for the copies left behind. The reconciliation check compares records and both vector layouts. Old transcripts, old context logs and backups are outside this `forget` operation.

## Take it to a review

- Where can a remembered fact live besides its original row?
- Does deletion follow every derived record, not only the first summary?
- How does the system detect missing or stale vector copies?
- Which historical records are kept after forgetting, and for how long?
