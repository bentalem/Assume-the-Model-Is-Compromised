# Database schema contract

Normative for `database/migrations/`. Derived from
[../docs/03-data-identity-authorization.md](../docs/03-data-identity-authorization.md).

## Rules that shape every table

1. `sp_migrator_role` owns the schema and every table. Runtime roles own **nothing**.
2. Every protected table carries `organization_id` and has RLS **enabled and forced**.
3. Grants are column-level where a tool needs only part of a row.
4. Runtime roles get no `ALL` grants — list the statements explicitly.
5. Tenant context is read from `current_setting('app.organization_id', true)` — set per transaction.

## Migration order

| # | Migration | Phase | Contents |
|---|---|---|---|
| `0001` | `roles_and_schema` | 1 | Roles, `app` schema, revoke public, default privileges |
| `0002` | `core_tenancy` | 1 | `organizations`, `users`, `memberships` + RLS |
| `0003` | `customers_orders` | 1 | `customers`, `orders` + RLS + grants |
| `0004` | `audit_events` | 1 | `audit_events` + append-only grants |
| `0005` | `orders_detail` | 2 | `order_items`, `shipments` + RLS |
| `0006` | `tickets` | 2 | `tickets`, `ticket_messages` + RLS |
| `0007` | `internal_notes` | 3 | `internal_notes` + insert policy |
| `0008` | `actions` | 4 | `action_requests`, `approval_decisions`, `action_jobs`, `action_executions` |

Each migration is forward-only, transactional where PostgreSQL allows, and ends with permission and
RLS smoke tests (`TS-3`).

## 0001 — Roles and schema

```sql
CREATE ROLE sp_migrator_role LOGIN PASSWORD :'migrator_password';
CREATE ROLE sp_api_role      LOGIN PASSWORD :'api_password'     NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sp_worker_role   LOGIN PASSWORD :'worker_password'  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sp_auditor_role  LOGIN PASSWORD :'auditor_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION sp_migrator_role;
GRANT USAGE ON SCHEMA app TO sp_api_role, sp_worker_role, sp_auditor_role;

ALTER DEFAULT PRIVILEGES FOR ROLE sp_migrator_role IN SCHEMA app
  REVOKE ALL ON TABLES FROM PUBLIC;
```

Helper used by every policy:

```sql
CREATE FUNCTION app.current_org() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.organization_id', true), '')::uuid
$$;

CREATE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;
```

`app.current_org()` returns `NULL` when context is missing, so every `USING` clause evaluates false —
this is what makes check `V-04` return zero rows.

## 0002 — Core tenancy

```sql
CREATE TABLE app.organizations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,          -- 'cedar', 'northwind'
  name        text NOT NULL,
  status      text NOT NULL DEFAULT 'active'
              CHECK (status IN ('active','suspended')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_subject text NOT NULL UNIQUE,     -- Keycloak 'sub'
  display_name     text NOT NULL,
  status           text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','disabled')),
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.memberships (
  user_id         uuid NOT NULL REFERENCES app.users(id),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  role            text NOT NULL
                  CHECK (role IN ('support_agent','support_manager','finance_approver','auditor')),
  status          text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','revoked')),
  granted_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organization_id, role)
);
CREATE INDEX memberships_user_active ON app.memberships (user_id) WHERE status = 'active';
```

`memberships` is read by the API **outside** tenant context (it is how tenant context is
established), so it is granted narrowly by subject rather than by RLS on `organization_id`:

```sql
GRANT SELECT ON app.memberships, app.organizations, app.users TO sp_api_role;

ALTER TABLE app.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memberships FORCE  ROW LEVEL SECURITY;
CREATE POLICY memberships_self ON app.memberships FOR SELECT TO sp_api_role
  USING (user_id = app.current_user_id() OR app.current_org() IS NOT DISTINCT FROM organization_id);
```

> **Bootstrapping note:** the API loads memberships with `SET LOCAL app.user_id` set and
> `app.organization_id` unset. The first clause of `memberships_self` is what makes that read work,
> and it is limited to the caller's own rows. Do not widen it.

## 0003 — Customers and orders

```sql
CREATE TABLE app.customers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  external_ref    text NOT NULL,
  full_name       text NOT NULL,
  email           text,
  assigned_team   text,
  sensitivity     text NOT NULL DEFAULT 'normal'
                  CHECK (sensitivity IN ('normal','restricted')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, external_ref)
);

CREATE TABLE app.orders (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  customer_id     uuid NOT NULL REFERENCES app.customers(id),
  order_number    text NOT NULL,             -- 'ORD-2001'
  status          text NOT NULL
                  CHECK (status IN ('placed','paid','shipped','delivered','cancelled','refunded')),
  currency        char(3) NOT NULL,
  total_amount    numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  placed_at       timestamptz NOT NULL,
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, order_number)
);
CREATE INDEX orders_org_number ON app.orders (organization_id, order_number);
```

`order_number` is unique **per organization**, not globally — the lookup is always
`WHERE order_number = $1` under tenant context, so a guessed number from another tenant matches
nothing (check `V-06`).

```sql
ALTER TABLE app.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.customers FORCE  ROW LEVEL SECURITY;
CREATE POLICY customers_tenant_read ON app.customers FOR SELECT TO sp_api_role
  USING (organization_id = app.current_org());

ALTER TABLE app.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.orders FORCE  ROW LEVEL SECURITY;
CREATE POLICY orders_tenant_read ON app.orders FOR SELECT TO sp_api_role
  USING (organization_id = app.current_org());

GRANT SELECT (id, organization_id, external_ref, full_name, email, assigned_team)
  ON app.customers TO sp_api_role;
GRANT SELECT (id, organization_id, customer_id, order_number, status, currency, total_amount, placed_at, updated_at)
  ON app.orders TO sp_api_role;
```

## 0004 — Audit events

```sql
CREATE TABLE app.audit_events (
  event_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at         timestamptz NOT NULL DEFAULT now(),
  request_id          text NOT NULL,
  trace_id            text,
  actor_type          text NOT NULL CHECK (actor_type IN ('user','workload')),
  actor_id            text NOT NULL,
  organization_id     uuid REFERENCES app.organizations(id),
  action              text NOT NULL,          -- 'order.read', 'refund.execute'
  resource_type       text,
  resource_id         text,
  decision            text NOT NULL
                      CHECK (decision IN ('allowed','denied','approved','rejected','succeeded','failed')),
  reason              text NOT NULL,
  policy_version      text,
  payload_hash        text,
  result_reference    text,
  previous_event_hash text,
  event_hash          text
);
CREATE INDEX audit_request ON app.audit_events (request_id);
CREATE INDEX audit_org_time ON app.audit_events (organization_id, occurred_at DESC);

GRANT INSERT ON app.audit_events TO sp_api_role, sp_worker_role;
GRANT SELECT ON app.audit_events TO sp_auditor_role;
-- deliberately no UPDATE or DELETE for any runtime role
```

Audit rows are append-only: no runtime role holds `UPDATE` or `DELETE`. The API does not read audit
events; only `sp_auditor_role` does.

## 0005–0006 — Order detail and tickets

```sql
CREATE TABLE app.order_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  order_id        uuid NOT NULL REFERENCES app.orders(id),
  sku             text NOT NULL,
  description     text NOT NULL,
  quantity        integer NOT NULL CHECK (quantity > 0),
  unit_amount     numeric(12,2) NOT NULL CHECK (unit_amount >= 0)
);

CREATE TABLE app.shipments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  order_id        uuid NOT NULL REFERENCES app.orders(id),
  carrier         text,
  tracking_ref    text,
  status          text NOT NULL
                  CHECK (status IN ('pending','in_transit','delivered','returned','lost')),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.tickets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  customer_id     uuid NOT NULL REFERENCES app.customers(id),
  ticket_number   text NOT NULL,              -- 'TKT-1001'
  subject         text NOT NULL,
  assigned_team   text,
  status          text NOT NULL CHECK (status IN ('open','pending','resolved','closed')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, ticket_number)
);

CREATE TABLE app.ticket_messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  ticket_id       uuid NOT NULL REFERENCES app.tickets(id),
  author_kind     text NOT NULL CHECK (author_kind IN ('customer','agent','system')),
  body            text NOT NULL,
  visibility      text NOT NULL DEFAULT 'public'
                  CHECK (visibility IN ('public','internal','restricted')),
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

Every one of these gets the same treatment as `orders`: `ENABLE` + `FORCE` RLS, a
`organization_id = app.current_org()` select policy for `sp_api_role`, and column-level `SELECT`
grants. `ticket_messages` additionally filters on `visibility` — the policy is per-role, and
`restricted` messages are excluded for `support_agent`.

> `ticket_messages.body` is the primary carrier of stored prompt-injection content (`TKT-1001`). It
> is data. Nothing downstream may interpret it as instruction.

## 0007 — Internal notes (first write)

```sql
CREATE TABLE app.internal_notes (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  ticket_id       uuid NOT NULL REFERENCES app.tickets(id),
  author_id       uuid NOT NULL REFERENCES app.users(id),
  body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
  created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app.internal_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.internal_notes FORCE  ROW LEVEL SECURITY;

CREATE POLICY notes_tenant_read ON app.internal_notes FOR SELECT TO sp_api_role
  USING (organization_id = app.current_org());

CREATE POLICY notes_tenant_insert ON app.internal_notes FOR INSERT TO sp_api_role
  WITH CHECK (
    organization_id = app.current_org()
    AND author_id   = app.current_user_id()
    AND EXISTS (SELECT 1 FROM app.tickets t
                WHERE t.id = ticket_id AND t.organization_id = app.current_org())
  );

GRANT SELECT, INSERT ON app.internal_notes TO sp_api_role;
```

The `author_id = app.current_user_id()` check is what makes an author supplied by the model
impossible to honor — the database refuses it even if application code is wrong (`P3-03`).

## 0008 — Actions, approvals, jobs, executions

```sql
CREATE TABLE app.action_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  requester_id    uuid NOT NULL REFERENCES app.users(id),
  action_type     text NOT NULL CHECK (action_type IN ('refund')),
  resource_type   text NOT NULL,
  resource_id     uuid NOT NULL,
  payload         jsonb NOT NULL,
  payload_hash    text NOT NULL,
  state           text NOT NULL DEFAULT 'PROPOSED'
                  CHECK (state IN ('PROPOSED','PENDING_APPROVAL','APPROVED','REJECTED',
                                   'QUEUED','EXECUTING','SUCCEEDED','FAILED','CANCELLED')),
  risk_level      text NOT NULL DEFAULT 'high',
  expires_at      timestamptz NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.approval_decisions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_request_id uuid NOT NULL REFERENCES app.action_requests(id),
  approver_id       uuid NOT NULL REFERENCES app.users(id),
  decision          text NOT NULL CHECK (decision IN ('approved','rejected')),
  approved_hash     text NOT NULL,           -- must equal action_requests.payload_hash
  comment           text,
  policy_version    text NOT NULL,
  decided_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT one_decision_per_request UNIQUE (action_request_id)
);

CREATE TABLE app.action_jobs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_request_id uuid NOT NULL REFERENCES app.action_requests(id),
  state             text NOT NULL DEFAULT 'QUEUED'
                    CHECK (state IN ('QUEUED','EXECUTING','SUCCEEDED','FAILED')),
  attempts          integer NOT NULL DEFAULT 0,
  lease_owner       text,
  lease_expires_at  timestamptz,
  available_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT one_job_per_request UNIQUE (action_request_id)
);
CREATE INDEX jobs_claimable ON app.action_jobs (state, available_at);

CREATE TABLE app.action_executions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id             uuid NOT NULL REFERENCES app.action_jobs(id),
  idempotency_key    text NOT NULL,
  provider           text NOT NULL,
  provider_reference text,
  outcome            text NOT NULL CHECK (outcome IN ('succeeded','failed','ambiguous')),
  started_at         timestamptz NOT NULL DEFAULT now(),
  finished_at        timestamptz,
  CONSTRAINT one_effect_per_key UNIQUE (idempotency_key)
);
```

Three constraints carry the whole duplicate-execution defense:

| Constraint | Prevents |
|---|---|
| `one_decision_per_request` | A second approval, or an approval replacing a rejection |
| `one_job_per_request` | Two queue entries for one approved action |
| `one_effect_per_key` | A retry producing a second provider effect (`T-012`) |

Atomic job claim — the only sanctioned way a worker takes a job:

```sql
UPDATE app.action_jobs
SET    state = 'EXECUTING',
       lease_owner = $1,
       lease_expires_at = now() + interval '5 minutes',
       attempts = attempts + 1
WHERE  id = (
  SELECT id FROM app.action_jobs
  WHERE  state = 'QUEUED' AND available_at <= now()
  ORDER  BY available_at
  FOR UPDATE SKIP LOCKED
  LIMIT  1
)
RETURNING id, action_request_id;
```

`FOR UPDATE SKIP LOCKED` is what makes two concurrent workers claim different jobs (`TS8-08`). A
crashed worker's lease expires and the row returns to `QUEUED`; it never stays stuck in `EXECUTING`
(`TS8-11`).

### Worker grants — deliberately narrow

```sql
GRANT SELECT (id, organization_id, requester_id, action_type, resource_type,
              resource_id, payload, payload_hash, state, expires_at)
  ON app.action_requests TO sp_worker_role;
GRANT UPDATE (state, updated_at)          ON app.action_requests TO sp_worker_role;
GRANT SELECT                              ON app.approval_decisions TO sp_worker_role;
GRANT SELECT, UPDATE                      ON app.action_jobs TO sp_worker_role;
GRANT SELECT, INSERT, UPDATE              ON app.action_executions TO sp_worker_role;
-- no grant at all on customers, orders, tickets, ticket_messages, internal_notes
```

The worker cannot read customer or order data (`TS3-04`). It gets what it needs from the frozen
`payload`.

## Seed data (`database/seeds/`)

Matches [../docs/08-local-build-runbook.md §2](../docs/08-local-build-runbook.md#2-test-data-baseline)
exactly. Repeatable — running it twice produces the same state.

- Organizations `cedar`, `northwind`.
- Users alice, bob, fiona, dana, mallory with memberships as listed.
- Customers and orders incl. `ORD-2001` (cedar) and `ORD-3001` (northwind).
- Ticket `TKT-1001` (cedar) with injection content in `ticket_messages.body`.

## Verification queries

```sql
-- V-03: runtime role holds no dangerous attribute
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
FROM pg_roles WHERE rolname LIKE 'sp\_%';

-- ST-04: runtime roles own nothing
SELECT c.relname, pg_get_userbyid(c.relowner) AS owner
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'app' AND pg_get_userbyid(c.relowner) <> 'sp_migrator_role';
-- expected: zero rows

-- every protected table has RLS enabled and forced
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'app' AND relkind = 'r' AND NOT (relrowsecurity AND relforcerowsecurity);
-- expected: zero rows
```
