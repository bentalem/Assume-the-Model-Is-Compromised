-- 0014 — The Range: challenge 2.3, the audit.
--
-- 2.1 tells the learner which table is broken. 2.3 does not: one table in `app` loses FORCE and the
-- learner has to find it with the catalogue query — the same query they would ask a client's DBA
-- for, against a schema of sixteen tables where fifteen are correct.
--
-- `order_items` is the target rather than something central, because that is how this failure
-- actually appears. Nobody forgets FORCE on the table the tenant story is about; they forget it on
-- the join table added six months later by someone who copied the migration above it and missed a
-- line.
--
-- The observation is deliberately narrow: `catalogue_unforced` returns only tables that are enabled
-- but not forced. Unarmed it returns nothing, which is what makes the flag unobtainable before the
-- learner has done anything — the property every flag in this product has to have.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.arm_order_items_force_off() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.order_items NO FORCE ROW LEVEL SECURITY $$;

CREATE FUNCTION range.restore_order_items_force() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ ALTER TABLE app.order_items FORCE ROW LEVEL SECURITY $$;

CREATE FUNCTION range.table_security_order_items()
RETURNS TABLE (table_name text, owner text, rls_enabled boolean, rls_forced boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  SELECT c.relname::text, pg_get_userbyid(c.relowner)::text,
         c.relrowsecurity, c.relforcerowsecurity
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app' AND c.relkind = 'r' AND c.relname = 'order_items';
$$;

-- Enabled but not forced — the exact shape of the failure, and nothing else. A learner who runs
-- this before arming anything gets an empty result, which is the honest answer for a system whose
-- controls are all holding.
CREATE FUNCTION range.catalogue_unforced()
RETURNS TABLE (table_name text, owner text, rls_enabled boolean, rls_forced boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  SELECT c.relname::text, pg_get_userbyid(c.relowner)::text,
         c.relrowsecurity, c.relforcerowsecurity
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app' AND c.relkind = 'r'
    AND c.relrowsecurity AND NOT c.relforcerowsecurity
  ORDER BY c.relname;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_order_items_force_off()',
    'range.restore_order_items_force()',
    'range.table_security_order_items()',
    'range.catalogue_unforced()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0014_range_mutations_audit');

RESET ROLE;
COMMIT;
