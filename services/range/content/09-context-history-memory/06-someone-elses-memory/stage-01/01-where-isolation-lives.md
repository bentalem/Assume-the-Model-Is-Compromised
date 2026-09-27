# A vector store needs a tenant boundary

Long-term memory lives in PostgreSQL, but Qdrant also keeps vectors **and copies of the text** so the service can search by meaning.

This lab has two Qdrant layouts:

| Layout | What separates organisations |
|---|---|
| One collection per organisation | A scoped token that cannot read another collection |
| One shared collection | A tenant filter that the application must include in every query |

Both layouts contain test data so you can switch without rebuilding the index.

## The safe read path

The memory service includes the user's organisation and ownership filters when it queries Qdrant. It then reads each candidate ID from PostgreSQL under row-level security. Qdrant proposes matches; PostgreSQL decides what may be returned.

## Your task

Compare a direct Qdrant query **without a tenant filter** in the two layouts. With separate collections, the credential cannot open another organisation's collection. In the shared collection, omitting the filter can return another organisation's points.

The lab's service still has the PostgreSQL check. The observation shows what a separate job or badly written direct query could expose if it skipped that check.

Challenge 9.6 is about **where the boundary lives**, not just whether today's application remembered a filter.
