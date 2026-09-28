# Start here: the data layer at a glance

Read these two architecture tabs before you start challenge 2.1. They explain the part of the system track 2 is about: the core PostgreSQL database, who connects to it as what, and how it decides which rows a request may see.

Track 1 ended at "the API knows who is asking". Track 2 is what happens next, one layer down. SupportPilot keeps tenants apart **twice**:

| Layer | Where it runs | What it decides |
|---|---|---|
| **The API's policy** | the API, asking OPA | may this person do this action on this record? |
| **Row-level security** | inside PostgreSQL | which rows exist at all, for this request |

The first layer is track 3. This track is the second one — the layer that still holds when the code above it is wrong.

## What is in the database

Everything lives in one schema, `app`, in the core PostgreSQL database. It holds sixteen tables:

| Group | Tables | Carries a tenant column? |
|---|---|---|
| Identity | `organizations`, `users`, `memberships` | memberships only |
| Business data | `customers`, `orders`, `order_items`, `shipments` | yes |
| Support | `tickets`, `ticket_messages`, `internal_notes` | yes |
| Refunds | `action_requests`, `approval_decisions`, `action_jobs`, `action_executions` | requests yes; the rest hang off a request |
| Evidence | `audit_events` | yes |
| Bookkeeping | `schema_migrations` | no — it is not tenant data, and has no row security |

Fifteen of them have row security **enabled and forced**. You will read that fact off the live catalogue in 2.1 and 2.3.

## Who connects as what

Every component logs in as its own database role. Each role holds only the grants it needs, and none of them is exempt from row security.

| Role | Used by | What it may do |
|---|---|---|
| `sp_migrator_role` | the one-shot `migrate` job only | **owns every table**; creates the schema, policies and grants |
| `sp_api_role` | the API | read and write business tables, through their policies; owns nothing |
| `sp_worker_role` | the refund worker | the refund tables only — it cannot read customers or orders |
| `sp_auditor_role` | nobody at run time | read the audit trail and nothing else |
| `sp_range_role` | the Range | `EXECUTE` on named functions in the `range` schema; no table grant at all |
| `sp_memory_lookup_role` | the memory service | call `app.resolve_subject` and nothing else |
| `supportpilot_admin` | the database's own bootstrap | a superuser, used once to create the roles above; no running service holds its password |

The detail that matters most for this track is in the first two rows: **the role that owns the tables is not the role the application connects as.** Challenge 2.1 is about why that separation is load-bearing.

## How the lab knows it is still true

None of this is left to memory. A smoke test (`database/tests/permissions_smoke.sql`) runs on every migration and fails the job if any runtime role owns an object or holds `SUPERUSER` or `BYPASSRLS`, if any table is not both enabled and forced, if the audit trail is not append-only, or if a row from another tenant is visible under a cedar context. With the stack running, `verify_local.py` checks from outside as well:

| Check | What it proves |
|---|---|
| `V-03` | the API's role cannot alter schema, grants, policies or roles |
| `V-04` | protected tables return zero rows when no request context is set |
| `V-12` | pooled connections keep no request context between requests |
| `V-16` | the worker's role cannot read customer or order data |

**Next:** what one request looks like from inside the database.
