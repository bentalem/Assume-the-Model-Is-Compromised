-- 0005 — Order items and shipments.
--
-- Same shape as every business table: organization_id, ENABLE + FORCE row security, a tenant
-- policy per runtime role, and column-level grants.

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE app.order_items (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  order_id         uuid NOT NULL REFERENCES app.orders(id),
  sku              text NOT NULL,
  description      text NOT NULL,
  quantity         integer NOT NULL CHECK (quantity > 0),
  unit_amount      numeric(12,2) NOT NULL CHECK (unit_amount >= 0)
);

CREATE TABLE app.shipments (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  order_id         uuid NOT NULL REFERENCES app.orders(id),
  carrier          text,
  tracking_ref     text,
  status           text NOT NULL CHECK (status IN ('pending', 'in_transit',
                                                   'delivered', 'returned', 'lost')),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX order_items_org_order ON app.order_items (organization_id, order_id);
CREATE INDEX shipments_org_order   ON app.shipments  (organization_id, order_id);

ALTER TABLE app.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.order_items FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.shipments   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.shipments   FORCE  ROW LEVEL SECURITY;

CREATE POLICY order_items_tenant_read ON app.order_items FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

CREATE POLICY shipments_tenant_read ON app.shipments FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

GRANT SELECT (id, organization_id, order_id, sku, description, quantity, unit_amount)
  ON app.order_items TO sp_api_role;

GRANT SELECT (id, organization_id, order_id, carrier, tracking_ref, status, updated_at)
  ON app.shipments TO sp_api_role;

INSERT INTO app.schema_migrations (version) VALUES ('0005_orders_detail');

RESET ROLE;
COMMIT;
