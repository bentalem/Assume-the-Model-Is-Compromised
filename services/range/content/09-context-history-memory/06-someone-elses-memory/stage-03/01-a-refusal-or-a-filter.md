# The store must protect data, not only the query

The service learns the organisation from the verified user, then queries Qdrant with ownership and status filters. In a shared collection it also adds an organisation filter.

Every candidate ID is then read again from PostgreSQL under row-level security. A candidate that belongs to another user or has been forgotten is not returned.

In the direct Qdrant observation, we deliberately remove the filter and skip the PostgreSQL check. This shows the difference between **a boundary the database enforces** and **a filter every caller must remember**.

A scoped token for one organisation's collection cannot read another collection. A shared-collection token can search the whole collection unless the query filters it.

## Take it to a review

- Which components can query the vector store directly?
- Can a missing tenant filter return another organisation's text?
- Are candidates checked again against current permissions in the source database?
- Does the store hold plaintext copies of memory as well as vectors?
