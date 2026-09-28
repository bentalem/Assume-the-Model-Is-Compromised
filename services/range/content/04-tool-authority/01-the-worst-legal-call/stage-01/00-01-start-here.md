# Start here: how a tool reaches the model

Read these two architecture tabs before you start challenge 4.1. They explain the part of the system track 4 is about: what a "tool" physically is in this lab, how it gets from code to the model, and what bounds each one.

A tool is not a separate program. It is **an API route**, described in a document the agent platform reads. The model never sees the code — only the description.

## The architecture

```text
API route code  (services/api/src/supportpilot_api/tools/*.py)
    |
    |  scripts/export_openapi.py  — generates the document from the running routes,
    |                               then audits it; a failing audit publishes nothing
    v
openapi/supportpilot-actions.json   — the action document
    |
    |  pasted into Onyx by an admin (LAB.md B10)
    v
Onyx agent  --->  the model reads each tool's name, summary and parameter schema
    |
    |  the model picks a tool and fills in its arguments
    v
the same API route, with the user's token  --->  the pipeline from tracks 1 to 3
```

Two copies of the tool list exist that you can check — the code and the document, compared whenever `export_openapi.py --check` runs — and one you cannot: what was pasted into Onyx. Challenge 8.1 is about that third copy.

## The seven tools

| Tool | Request | What the model supplies | Effect |
|---|---|---|---|
| `get_order` | `GET /v1/orders/{order_number}` | an order number, two yes/no options | read |
| `search_customers` | `GET /v1/customers` | a query `q`, a `limit`, a `cursor` | read — **a set** |
| `get_customer` | `GET /v1/customers/{customer_ref}` | a customer reference | read |
| `get_ticket` | `GET /v1/tickets/{ticket_number}` | a ticket number, a `limit`, a `cursor` for its messages | read |
| `add_internal_note` | `POST /v1/tickets/{ticket_number}/notes` | a ticket number; a body with the note text and the ticket status it expects | writes a row in this database |
| `propose_refund` | `POST /v1/actions/refunds` | a body: order number, amount, currency, reason, optional note | writes a **pending** request; moves no money |
| `get_action_status` | `GET /v1/actions/{action_id}` | an action id | read |

Six of them name one record. One takes a query and lets the caller choose the set — challenges 4.1 and 4.3.

## Who decides what

| Decided by | What |
|---|---|
| **The model** | which tool, and every argument the schema allows |
| **The schema** | the shape of each argument: type, pattern, length, allowed values, no extra fields |
| **The server** | who the caller is, which tenant, which role — never an argument |
| **The policy** | whether the call is allowed, which fields come back, the page size |
| **The database** | which rows exist for this tenant |
| **Nobody** | how many calls one session makes, in total |

That last row is where most of this track lives. Everything above it is evaluated **per call**.

**Next:** each of those bounds in detail, and the gate the document passes through before it is published.
