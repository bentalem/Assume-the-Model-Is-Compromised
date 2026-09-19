-- 0012 — Fix the column types the 2.1 observations return.
--
-- app.orders.currency is character(3), not text, and PL/pgSQL compares a RETURNS TABLE signature
-- against the query's actual types rather than coercing them. The function raised
-- "structure of query does not match function result type" on its first call.
--
-- Worth noting how it was found: the function compiled, the migration applied, the smoke tests
-- passed, and the failure only appeared when something ran it. A definition that installs cleanly
-- is not a definition that works — which is the same distinction challenge 2.1 is about, arriving
-- from the other direction.
--
-- 0011 is left as applied rather than edited. A migration that has run is history.

BEGIN;

SET ROLE sp_migrator_role;

CREATE OR REPLACE FUNCTION range.observe_orders_as_owner()
RETURNS TABLE (tenant text, order_number text, status text, currency text, total_amount numeric)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
BEGIN
  PERFORM set_config('app.organization_id', '11111111-1111-1111-1111-111111111111', true);

  RETURN QUERY
  SELECT o.organization_id::text, o.order_number::text, o.status::text,
         o.currency::text, o.total_amount
  FROM app.orders o
  ORDER BY o.order_number
  LIMIT 25;
END
$$;

CREATE OR REPLACE FUNCTION range.observe_orders_as_api()
RETURNS TABLE (tenant text, order_number text, status text, currency text, total_amount numeric)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
BEGIN
  PERFORM set_config('app.organization_id', '11111111-1111-1111-1111-111111111111', true);
  SET LOCAL ROLE sp_api_role;

  RETURN QUERY
  SELECT o.organization_id::text, o.order_number::text, o.status::text,
         o.currency::text, o.total_amount
  FROM app.orders o
  ORDER BY o.order_number
  LIMIT 25;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0012_range_observation_types');

RESET ROLE;
COMMIT;
