# Tenant isolation: the system behind track 2

This is the same architecture lesson shown in challenge 2.1's two opening Learn tabs. Read it before starting track 2. No terminal is needed for the challenges.

## 1. Start here: the data layer at a glance

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

## 2. Part 1: one request, inside the database

Every database call the API makes goes through one function: `Database.transaction()` in `services/api/src/supportpilot_api/db.py`. No route opens a connection itself, so there is exactly one place where request context is set — and one place to review.

## The exact order

For alice reading `ORD-2001`:

1. **Borrow a connection** from the pool. It is already logged in as `sp_api_role`.
2. **Open a transaction.**
3. **Set the request context** with three calls, each `set_config(name, value, true)`. The `true` makes each value **transaction-local** — it disappears at the end of step 5.
4. **Run the query.** PostgreSQL rewrites it with the table's row policy before running it.
5. **Commit.** The three values vanish with the transaction.
6. **Reset the connection** (`RESET ALL`) as it goes back to the pool — a second line of defence behind step 5.

The three values set in step 3:

| Setting | Holds | Read back by |
|---|---|---|
| `app.user_id` | the person's internal id | `app.current_user_id()` |
| `app.organization_id` | the tenant this request is about | `app.current_org()` |
| `app.roles` | the person's roles **in that tenant** | `app.current_roles()` |

All three come from track 1's lookup — the verified token, then `app.memberships` — never from the request.

## What a policy looks like

A row policy is a condition PostgreSQL adds to every query on its table. The one on `orders`:

```sql
CREATE POLICY orders_tenant_read ON app.orders FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());
```

`app.current_org()` returns `NULL` when the setting is empty. `organization_id = NULL` is never true, so **no context means no rows** — never all rows. That is what `V-04` measures.

Some policies read the roles too. On `ticket_messages`, a restricted message is visible only when `app.current_roles()` includes `support_manager` or `auditor` — which is why track 1's demotion also changes what bob can read in a ticket.

## What decides whether the policy runs at all

Having a correct policy is not the same as the policy being used. For every query, PostgreSQL first asks:

| Question | If the answer is… | …the policy is |
|---|---|---|
| Is row security **enabled** on the table? | no | skipped: every row the grants allow comes back |
| Does the role have **`SUPERUSER`** or **`BYPASSRLS`**? | yes | skipped |
| Does the role **own** the table, with **`FORCE`** off? | yes | skipped |
| Otherwise | — | applied |

In this lab every answer is the safe one: every tenant table is enabled **and** forced, no runtime role bypasses anything, and `sp_api_role` owns nothing. The next tabs explain each question in depth — and 2.1 lets you break the third.

## Which challenge tests each part?

| Challenge | The question you will answer |
|---|---|
| 2.1 | Can a correct policy filter nothing? What decides whether it is consulted? |
| 2.2 | Why must request context be transaction-local on a pooled connection, and what does `V-12` prove? |
| 2.3 | In a schema you did not write, which table is not actually protected? |

**Read the code:** `services/api/src/supportpilot_api/db.py`, `database/migrations/0001_roles_and_schema.sql` and `0003_customers_orders.sql`.

**Now start challenge 2.1.** The next four tabs explain row-level security in depth before you break it.
