-- 0011 — The Range: the mutations and observations for challenge 2.1.
--
-- Every entry here is a named function that takes no argument naming a target. There is no
-- `set_row_security(table, enabled, forced)`, because a function with a target parameter is a
-- generic tool with a business name — the exact finding track 4 teaches people to recognise, and
-- it would be embarrassing to ship it in the service that teaches it.
--
-- So: one function per mutation, the table written into the body, and the Range's whole vocabulary
-- is the list of functions it holds EXECUTE on.
--
-- Each mutation has an inverse in this file, and `scripts/range_suite.py` arms every one, probes
-- armed, restores, and probes correct. A mutation whose round trip is not in that suite is a
-- mutation that can leave a learner's lab quietly wrong.

BEGIN;

SET ROLE sp_migrator_role;

-- ------------------------------------------------------------------------------------------------
-- Mutations — app.orders row security.
--
-- ENABLE and FORCE are separate flags and the challenge is the difference between them, so they are
-- separate mutations. A learner who can only toggle one of them has been shown a fact; a learner
-- who can walk the truth table has been taught a mechanism.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.arm_orders_force_off() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.orders NO FORCE ROW LEVEL SECURITY $$;

CREATE FUNCTION range.restore_orders_force() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.orders FORCE ROW LEVEL SECURITY $$;

CREATE FUNCTION range.arm_orders_rls_disable() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.orders DISABLE ROW LEVEL SECURITY $$;

CREATE FUNCTION range.restore_orders_rls() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.orders ENABLE ROW LEVEL SECURITY $$;

-- ------------------------------------------------------------------------------------------------
-- Observations.
--
-- Both set a cedar tenant context first, exactly as the API does on every request, and both are
-- capped. The cap is not a display convenience: an observation with no cap is a bulk read waiting
-- for somebody to arm the wrong thing, and the lab's own rule 11 is to bound every response.
--
-- The difference between them is the whole lesson. `as_owner` runs with the rights of the function
-- owner, which is the role that owns app.orders — that is what "the application connects as the
-- owning role" means, reproduced without moving a credential anywhere. `as_api` switches to
-- sp_api_role, which owns nothing, and is the control group.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.observe_orders_as_owner()
RETURNS TABLE (tenant text, order_number text, status text, currency text, total_amount numeric)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
BEGIN
  -- Cedar, the same organization the API would put in context for alice.
  PERFORM set_config('app.organization_id', '11111111-1111-1111-1111-111111111111', true);

  RETURN QUERY
  SELECT o.organization_id::text, o.order_number, o.status, o.currency, o.total_amount
  FROM app.orders o
  ORDER BY o.order_number
  LIMIT 25;
END
$$;

CREATE FUNCTION range.observe_orders_as_api()
RETURNS TABLE (tenant text, order_number text, status text, currency text, total_amount numeric)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
BEGIN
  PERFORM set_config('app.organization_id', '11111111-1111-1111-1111-111111111111', true);

  -- SET LOCAL, so the role reverts when the statement's transaction ends even if this function
  -- raises. A role switch that outlives its function is how a helper becomes a privilege.
  SET LOCAL ROLE sp_api_role;

  RETURN QUERY
  SELECT o.organization_id::text, o.order_number, o.status, o.currency, o.total_amount
  FROM app.orders o
  ORDER BY o.order_number
  LIMIT 25;
END
$$;

-- ------------------------------------------------------------------------------------------------
-- Ownership and grants. Nothing here is granted to PUBLIC, and nothing is granted by default: a
-- function added to this schema later is unreachable until a migration names it.
-- ------------------------------------------------------------------------------------------------
DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_orders_force_off()',
    'range.restore_orders_force()',
    'range.arm_orders_rls_disable()',
    'range.restore_orders_rls()',
    'range.observe_orders_as_owner()',
    'range.observe_orders_as_api()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

-- The owner-side observation reads across tenants by design, so app.orders needs a policy that
-- admits the migration role. Without it, FORCE row security applies to the owner and `as_owner`
-- returns nothing in *every* configuration — which would look exactly like a working control and
-- teach the opposite of the lesson.
CREATE POLICY orders_migrator_read ON app.orders FOR SELECT TO sp_migrator_role
USING (true);

INSERT INTO app.schema_migrations (version) VALUES ('0011_range_mutations_rls');

RESET ROLE;
COMMIT;
