-- Local test data baseline. Fixed by SP-PLAN-003 §2 — the test suites depend on these names.
-- Repeatable: running it twice produces the same state.
--
-- Realistic but entirely fictional. Never load real customer data here.

-- Runs as the bootstrap administrator, not as sp_migrator_role. Protected tables use FORCE ROW
-- LEVEL SECURITY, which applies to the table owner as well, and there is deliberately no INSERT
-- policy granting the migration role a way past tenant rules. Loading fixtures is an
-- administrative act, so it uses the administrative identity.

BEGIN;

-- ------------------------------------------------------------------------------------------------
-- Organizations
-- ------------------------------------------------------------------------------------------------
INSERT INTO app.organizations (id, slug, name) VALUES
  ('11111111-1111-1111-1111-111111111111', 'cedar',     'Cedar Retail Group'),
  ('22222222-2222-2222-2222-222222222222', 'northwind', 'Northwind Supply Co')
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name;

-- ------------------------------------------------------------------------------------------------
-- Users. identity_subject matches the Keycloak user id in the realm import.
-- ------------------------------------------------------------------------------------------------
INSERT INTO app.users (id, identity_subject, display_name) VALUES
  ('a1111111-1111-1111-1111-111111111111', 'alice-id',   'Alice Nguyen'),
  ('b1111111-1111-1111-1111-111111111111', 'bob-id',     'Bob Ferreira'),
  ('f1111111-1111-1111-1111-111111111111', 'fiona-id',   'Fiona Adeyemi'),
  ('d1111111-1111-1111-1111-111111111111', 'dana-id',    'Dana Kovacs'),
  ('c1111111-1111-1111-1111-111111111111', 'mallory-id', 'Mallory Okonkwo')
ON CONFLICT (identity_subject) DO UPDATE SET display_name = EXCLUDED.display_name;

-- ------------------------------------------------------------------------------------------------
-- Memberships. mallory is in northwind only — every cross-tenant test relies on that.
-- ------------------------------------------------------------------------------------------------
INSERT INTO app.memberships (user_id, organization_id, role) VALUES
  ('a1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'support_agent'),
  ('b1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'support_manager'),
  ('f1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'finance_approver'),
  ('d1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'auditor'),
  ('c1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'support_agent')
ON CONFLICT (user_id, organization_id, role) DO UPDATE SET status = 'active';

-- ------------------------------------------------------------------------------------------------
-- Customers
-- ------------------------------------------------------------------------------------------------
INSERT INTO app.customers (id, organization_id, external_ref, full_name, email, assigned_team, sensitivity) VALUES
  ('c0000001-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'CUS-4001', 'Priya Raman',      'priya.raman@example.invalid',   'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',
   'CUS-4002', 'Tomas Lindqvist',  'tomas.l@example.invalid',        'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111',
   'CUS-4003', 'Wren Abbott',      'wren.abbott@example.invalid',    'team-south', 'restricted'),
  ('c0000002-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
   'CUS-9001', 'Hugo Marchetti',   'hugo.m@example.invalid',         'team-west',  'normal')
ON CONFLICT (organization_id, external_ref) DO UPDATE SET full_name = EXCLUDED.full_name;

-- ------------------------------------------------------------------------------------------------
-- Orders.
--   ORD-2001 (cedar)     — the first protected read.
--   ORD-3001 (northwind) — alice must never be able to read this.
-- ------------------------------------------------------------------------------------------------
INSERT INTO app.orders (id, organization_id, customer_id, order_number, status,
                        currency, total_amount, placed_at) VALUES
  ('00000001-0000-0000-0000-000000002001', '11111111-1111-1111-1111-111111111111',
   'c0000001-0000-0000-0000-000000000001', 'ORD-2001', 'shipped',   'USD', 149.90, '2026-08-14T09:12:00Z'),
  ('00000001-0000-0000-0000-000000002002', '11111111-1111-1111-1111-111111111111',
   'c0000001-0000-0000-0000-000000000002', 'ORD-2002', 'delivered', 'USD',  64.00, '2026-08-02T14:40:00Z'),
  ('00000001-0000-0000-0000-000000002003', '11111111-1111-1111-1111-111111111111',
   'c0000001-0000-0000-0000-000000000003', 'ORD-2003', 'cancelled', 'USD', 310.25, '2026-07-28T08:05:00Z'),
  ('00000002-0000-0000-0000-000000003001', '22222222-2222-2222-2222-222222222222',
   'c0000002-0000-0000-0000-000000000001', 'ORD-3001', 'paid',      'EUR', 512.00, '2026-08-20T16:30:00Z')
ON CONFLICT (organization_id, order_number) DO UPDATE SET status = EXCLUDED.status;

COMMIT;
