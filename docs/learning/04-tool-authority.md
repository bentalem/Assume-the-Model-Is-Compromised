# Tool authority: the system behind track 4

This is the same architecture lesson shown in challenge 4.1's two opening Learn tabs. Read it before starting track 4. No terminal is needed for the challenges.

## 1. Start here: how a tool reaches the model

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

## 2. Part 1: what bounds a tool

A tool's authority is everything a legal call can do. In this lab it is bounded in five places, and each one bounds something different.

| Bound | Where it lives | What it limits | Example |
|---|---|---|---|
| **The argument schema** | the Pydantic models in `tools/*.py`, published in the document | the shape of what the model can send | `order_number` must match `^ORD-[0-9]{4,12}$`; a body with an unknown field is refused |
| **Server-derived identity** | the pipeline (track 1) | who the call acts for | no tool has a `user_id`, `organization_id` or `role` argument |
| **The policy decision** | OPA (track 3) | whether this call is allowed, and its obligations | `max_results: 25` on a search; `allowed_fields` on a restricted customer |
| **Row security** | PostgreSQL (track 2) | which tenant's rows exist | another tenant's order does not exist for this caller |
| **Propose, approve, execute** | the refund tables and the worker (track 6) | whether an effect happens at all | `propose_refund` can only create a pending request |

All five are evaluated **for one call**. None of them counts calls.

## What bounds a session

Nothing in this repository. The budget you may have seen — `AGENT_MAX_TOOL_CALLS=8` in `.env.example` — is not read by any service here. The same number appears as a setting you type into Onyx by hand when you build the agent (LAB.md, B11): Onyx stops a single turn after eight tool calls, if someone set it. Nothing stops the next turn, and nothing totals a session.

## The gate the document passes through

`scripts/export_openapi.py` generates the action document from the running routes, then refuses to write it if any rule fails. With `--check` it also compares the committed document with the running code. Both happen only when somebody runs the script — nothing in the repository runs it for them.

| Rule | About |
|---|---|
| Every operation is on the approved list | the name — a new tool needs someone to add it by hand |
| No parameter is named `user_id`, `role`, `approved`, … | the name |
| No header is exposed to the model | the shape |
| Every string parameter has a pattern, a maximum length or a fixed value set | the shape |
| No query parameter is an array | the shape |
| Every operation has a summary, and every success response has a schema | the shape |
| No schema allows extra properties; every array has a maximum length | the shape |

Notice what the list does not contain. Challenge 4.2 asks you to find it.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 4.1 | Of the seven tools, which grants the most authority in one legal call? |
| 4.2 | Could any argument turn a tool into a generic one — and would the gate notice? |
| 4.3 | What do permitted calls add up to across a session? |
| 4.4 | Does anything send data out of this system — and what would a tool that did need? |

**Read the code:** `services/api/src/supportpilot_api/tools/`, `scripts/export_openapi.py`, `openapi/supportpilot-actions.json`.

**Now start challenge 4.1.**
