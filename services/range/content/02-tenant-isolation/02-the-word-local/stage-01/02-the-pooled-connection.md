# The pooled connection

## Where they stop being the same

`SET LOCAL` is scoped to the transaction. `SET` is scoped to the **session** — which means, on a
pooled connection, to the connection.

That distinction is invisible until the transaction ends. Here is the sequence that matters, and it
is worth reading slowly because it is the entire challenge:

| | With `SET LOCAL` | With `SET` |
|---|---|---|
| Request 1 arrives, takes a connection from the pool | — | — |
| sets context, runs its query | context set | context set |
| transaction ends, connection returns to the pool | **context gone** | **context still set** |
| Request 2 arrives, gets the same connection | — | — |
| ...and forgets to set context | no context: policies fail closed | **request 1's context** |

That last cell is the bug. Request 2 does not get an error and does not get nothing. It gets
somebody else's tenant, with every policy working perfectly, because the policies were told a lie
about who was asking.

## Where the value goes when the transaction ends

The transaction-scoped value is discarded at `COMMIT`. The session-scoped one is not: it stays on
the connection, and a connection pool hands that connection to the next request.

So two calls made in the same breath, on the same connection, have different lifetimes — and the
longer-lived one is the one nobody chose deliberately. It survives into a request made by a
different user, in a different tenant, and every policy downstream reads it and believes it.
