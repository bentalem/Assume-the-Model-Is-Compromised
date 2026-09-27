# Where isolation lives in a vector store

Long-term memory is usually a vector database — Qdrant, Pinecone, Weaviate, or pgvector — with an
embedding model that turns each memory into a vector. Recall is a similarity search.

There are two ways to keep tenants apart, and they are not equivalent.

| Layout | What separates cedar from northwind | If the application forgets |
|---|---|---|
| **One collection per tenant**, a credential scoped to each | the store: cedar's credential cannot open northwind's collection | the store refuses |
| **One shared collection**, a tenant field on every point | a filter the application adds to every query | the query returns both |

The shared layout is not a mistake someone made. It is what vector stores recommend for many
tenants, because thousands of small collections are expensive — Qdrant's own
[multitenancy guidance](https://qdrant.tech/documentation/manage-data/multitenancy/) describes one
collection partitioned by a payload field, indexed with `is_tenant`. The index makes the filter
fast. Nothing makes it mandatory.

This lab's service writes both layouts, so arming the shared layout needs no re-indexing — a lab
artifact, not something a real deployment would do. Its credentials follow the per-tenant design:
scoped tokens, and nobody at runtime holds the store's API key.
