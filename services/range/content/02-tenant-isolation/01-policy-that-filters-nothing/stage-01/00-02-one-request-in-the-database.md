# Part 1: one request, inside the database

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
