-- 0015 — `catalogue_unforced` was under-reporting the worse failure.
--
-- Its condition was `relrowsecurity AND NOT relforcerowsecurity` — enabled but not forced. A table
-- with row security *disabled entirely* does not match that, so the observation returned nothing
-- while app.orders was sitting at enabled=false, forced=false.
--
-- That is a lie by omission in an auditing tool: a learner runs "show me the tables that are not
-- protected", gets an empty result, and concludes the schema is clean while one table has no row
-- security at all. The empty result was the most reassuring possible answer to the worst possible
-- state.
--
-- It was found because the migration job's smoke test refused to run on the armed lab and named the
-- table, while this observation had just said there was nothing to report. Two instruments
-- disagreed and the stricter one was right.
--
-- The condition is now "not fully protected", with a column saying which way.

BEGIN;

SET ROLE sp_migrator_role;

DROP FUNCTION range.catalogue_unforced();

CREATE FUNCTION range.catalogue_unforced()
RETURNS TABLE (table_name text, owner text, rls_enabled boolean, rls_forced boolean, problem text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  SELECT c.relname::text,
         pg_get_userbyid(c.relowner)::text,
         c.relrowsecurity,
         c.relforcerowsecurity,
         CASE
           WHEN NOT c.relrowsecurity THEN 'row security is disabled entirely'
           ELSE 'enabled, but the owner is exempt'
         END
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app'
    AND c.relkind = 'r'
    -- schema_migrations carries no tenant data and is deliberately unprotected, exactly as the
    -- lab's own smoke test excludes it. An audit that reports a known, reasoned exception as a
    -- finding trains people to ignore its output.
    AND c.relname <> 'schema_migrations'
    AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
  ORDER BY c.relname;
$$;

ALTER FUNCTION range.catalogue_unforced() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.catalogue_unforced() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.catalogue_unforced() TO sp_range_role;

INSERT INTO app.schema_migrations (version) VALUES ('0015_range_unforced_reports_disabled');

RESET ROLE;
COMMIT;
