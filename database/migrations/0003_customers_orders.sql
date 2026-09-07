-- 0003 — Customers and orders. The first protected business objects.

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE app.customers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  external_ref     text NOT NULL,
  full_name        text NOT NULL,
  email            text,
  assigned_team    text,
  sensitivity      text NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('normal', 'restricted')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, external_ref)
);

CREATE TABLE app.orders (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  customer_id      uuid NOT NULL REFERENCES app.customers(id),
  order_number     text NOT NULL,
  status           text NOT NULL CHECK (status IN ('placed', 'paid', 'shipped',
                                                   'delivered', 'cancelled', 'refunded')),
  currency         char(3) NOT NULL,
  total_amount     numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  placed_at        timestamptz NOT NULL,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  -- Unique per organization, not globally. A guessed order number from another tenant therefore
  -- matches nothing under the caller's tenant context, independently of the policy check.
  UNIQUE (organization_id, order_number)
);

CREATE INDEX orders_org_number  ON app.orders (organization_id, order_number);
CREATE INDEX orders_org_customer ON app.orders (organization_id, customer_id);
CREATE INDEX customers_org_name ON app.customers (organization_id, lower(full_name));

-- ------------------------------------------------------------------------------------------------
-- Row security. Same shape for every business table: tenant equality, per runtime role.
-- ------------------------------------------------------------------------------------------------
ALTER TABLE app.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.customers FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.orders    ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.orders    FORCE  ROW LEVEL SECURITY;

CREATE POLICY customers_tenant_read ON app.customers FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

CREATE POLICY orders_tenant_read ON app.orders FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

-- ------------------------------------------------------------------------------------------------
-- Grants
-- ------------------------------------------------------------------------------------------------
GRANT SELECT (id, organization_id, external_ref, full_name, email, assigned_team, sensitivity)
  ON app.customers TO sp_api_role;

GRANT SELECT (id, organization_id, customer_id, order_number, status,
              currency, total_amount, placed_at, updated_at)
  ON app.orders TO sp_api_role;

INSERT INTO app.schema_migrations (version) VALUES ('0003_customers_orders');

RESET ROLE;
COMMIT;
