# A refusal, or a filter

What the service does on every recall and every context build:

1. **Resolves the caller's organisation** from the core database — never from the request.
2. **Chooses the collection** from the layout setting: `memories__cedar` per tenant, or `memories__shared`.
3. **Uses the credential for that collection** — a token that names it and nothing else.
4. **Adds the filter**: owner, and in the shared layout also `org_id`.
5. **Re-reads every candidate from memory-db, under row-level security,** before returning it. The vector store only proposes; the database decides.

Step 5 means that in this lab, even the shared layout would not have leaked through the service:
memory-db would have dropped the northwind row. That is two layers, and it is the lab's rule four
applied to a new store. The observation you ran removed step 4 and skipped step 5 — which is what a
second service, a batch job, an analytics export or a hand-written query against the same store
would have done.

## The question to ask of any vector store

> **If one query left out its tenant filter, what would the store do?**

"Return the other tenant's data" means isolation lives in every piece of code that will ever query
it. "Refuse" means it lives in the store and its credentials. Per tenant, Qdrant refused cedar's
token on northwind's collection with a 403 — measured, not assumed. Shared, there was nothing to
refuse: the token was for the whole collection.
