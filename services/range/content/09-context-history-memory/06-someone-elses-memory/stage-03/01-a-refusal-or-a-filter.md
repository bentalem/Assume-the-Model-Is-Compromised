# Why the collection layout changed the result

## What your result proves

With one collection per organisation, the token scoped to Cedar's collection could not open Northwind's collection. The vector store itself refused the request.

With one shared collection, the same kind of direct query reached records from different organisations when the tenant filter was left out. The request did not need to break a password or a model. It only needed a caller that forgot to send the filter.

## What the normal service does differently

This challenge deliberately makes a **direct Qdrant query** without the required filter. It is not evidence that the normal memory API leaks another organisation's records.

The real service obtains the organisation from the verified user and adds owner and tenant filters to its Qdrant query. It then reads each candidate ID from PostgreSQL under row-level security. A candidate that the caller cannot read in PostgreSQL is not returned by the memory API.

The lab writes test data to both Qdrant layouts so you can compare them without re-indexing. A production system would usually choose one.

## What each layout depends on

Separate collections can use scoped credentials: a credential limited to Cedar cannot access Northwind's collection. This gives the storage service a boundary of its own.

A shared collection depends on every direct reader supplying the correct tenant filter. An index on the tenant field makes that filter faster; it does not make the filter mandatory. Background jobs, analytics and other services need the same check if they read Qdrant directly.

Qdrant also stores text in each point's payload. These records should be treated as sensitive data, not harmless numerical vectors.

## Take it to a review

- Which services and jobs can reach the vector store without going through the memory API?
- Does each connection have a token limited to only the collections it needs?
- What happens if a direct query omits the tenant filter?
- Do all search results pass a second access check before they reach an end user or a model?
