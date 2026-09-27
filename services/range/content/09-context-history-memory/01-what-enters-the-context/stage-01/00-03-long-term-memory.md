# Part 2: long-term memory

History keeps the conversation. **Long-term memory keeps selected facts** that might help in a later conversation.

For example, the user tells the agent that they prefer short incident reports. The model may suggest saving this preference so it does not need to ask again tomorrow.

But a sentence in a ticket is not the same as the user's request to remember it. The model might be tricked into saving a malicious instruction. That is why our memory service separates **saving** from **confirming**.

## The life of a memory

```text
Model calls remember
       |
       v
PostgreSQL: new record, status = unconfirmed
       |
       | user confirms through a runtime-only route
       v
status = confirmed
       |
       v
Eligible for future context and recall
       |
       | owner calls forget
       v
Original, derived records and vector copies are retired
```

The model's `remember` tool only accepts text. The service decides the owner, organisation, source channel and initial status. A model-written memory is **unconfirmed by default**.

The route that confirms a memory is **not a model tool**. The runtime must call it on behalf of the user. Only confirmed records may enter the model's future context.

## Why there are two databases

`mem.records` in PostgreSQL is the **source of truth**. It holds the text, owner, organisation, source, status, confirmation, creation time and `derived_from` link for summaries.

Qdrant is a **search copy**. A local embedding model turns the text into a vector with **384 numbers**. Qdrant stores that vector **and a copy of the text** so the service can find facts with similar meanings.

The lab writes to two layouts: one Qdrant collection per organisation, and one shared collection with a tenant field. This double write is for challenge 9.6. A real deployment does not need both.

## How saving works across both stores

1. The service checks the user's identity and refuses recognised credentials as long-term memory.
2. It writes the fact, an audit event and an `outbox` job **in one PostgreSQL transaction**.
3. After commit, it asks the local embedding service to turn the text into numbers.
4. It sends the vector and payload to Qdrant, then marks the outbox job as applied.

PostgreSQL and Qdrant cannot commit one shared transaction. If Qdrant is unavailable, the PostgreSQL record still exists and the outbox job remains pending. A reconciliation check compares the stores and reports missing or stale copies.

## Two different read paths

**Automatic context:** select the user's **eight newest confirmed memories from PostgreSQL first**. Qdrant can change the order of those eight based on the new question. It does **not** select a different eight. If Qdrant is down, the same records can be shown by time.

**The `recall` tool:** search Qdrant for up to **30** candidate IDs. Then read those IDs from PostgreSQL under row-level security, returning only records the user is still allowed to see and that are confirmed. Results are paged, with up to **ten** per page.

Qdrant suggests which record may be relevant. PostgreSQL decides whether it may be returned.

## Summaries and forgetting

The runtime can make a short record from an existing memory. **In this lab, summary creation shortens text; it does not call a language model.** The new record points to its source through `derived_from`.

A full `forget` follows these links, marks the original and every derived record as forgotten, and requests deletion of their Qdrant copies. It does **not** delete old transcripts, earlier context logs or backups.

Challenge 9.5 tests who confirms a memory. Challenge 9.6 tests tenant separation in Qdrant. Challenge 9.8 tests what forgetting must remove.

**Read the code:** `memories.py`, `vectors.py` and `database/memory/migrations/0003_records.sql`.
