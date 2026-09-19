-- Permission and RLS smoke tests (TS-3, ST-04).
--
-- Runs at the end of every migration. Any failure aborts the migration job, so a schema change that
-- weakens a boundary cannot reach a running environment.

\set ON_ERROR_STOP on

DO $$
DECLARE
  offenders text;
  n integer;
BEGIN
  -- ----------------------------------------------------------------------------------------------
  -- 1. No runtime role holds a dangerous attribute (V-03).
  -- ----------------------------------------------------------------------------------------------
  SELECT string_agg(rolname, ', ') INTO offenders
  FROM pg_roles
  WHERE rolname IN ('sp_api_role', 'sp_worker_role', 'sp_auditor_role')
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: runtime role holds a dangerous attribute: %', offenders;
  END IF;

  -- ----------------------------------------------------------------------------------------------
  -- 2. Runtime roles own nothing in the app schema.
  -- ----------------------------------------------------------------------------------------------
  SELECT string_agg(c.relname || ' owned by ' || pg_get_userbyid(c.relowner), ', ') INTO offenders
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app'
    AND c.relkind IN ('r', 'v', 'm', 'S')
    AND pg_get_userbyid(c.relowner) <> 'sp_migrator_role';
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: object not owned by sp_migrator_role: %', offenders;
  END IF;

  -- ----------------------------------------------------------------------------------------------
  -- 3. Every table has RLS enabled AND forced.
  -- ----------------------------------------------------------------------------------------------
  SELECT string_agg(c.relname, ', ') INTO offenders
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app'
    AND c.relkind = 'r'
    AND c.relname <> 'schema_migrations'
    AND NOT (c.relrowsecurity AND c.relforcerowsecurity);
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: table without ENABLE+FORCE row level security: %', offenders;
  END IF;

  -- ----------------------------------------------------------------------------------------------
  -- 4. No runtime role can amend audit evidence.
  -- ----------------------------------------------------------------------------------------------
  SELECT string_agg(grantee || ':' || privilege_type, ', ') INTO offenders
  FROM information_schema.table_privileges
  WHERE table_schema = 'app' AND table_name = 'audit_events'
    AND privilege_type IN ('UPDATE', 'DELETE', 'TRUNCATE')
    AND grantee IN ('sp_api_role', 'sp_worker_role', 'sp_auditor_role');
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: audit_events is not append-only: %', offenders;
  END IF;

  -- ----------------------------------------------------------------------------------------------
  -- 5. No role holds table-wide ALL on a business table.
  -- ----------------------------------------------------------------------------------------------
  SELECT string_agg(DISTINCT grantee || ' on ' || table_name, ', ') INTO offenders
  FROM information_schema.table_privileges
  WHERE table_schema = 'app'
    AND grantee IN ('sp_api_role', 'sp_worker_role', 'sp_auditor_role')
    AND privilege_type IN ('TRUNCATE', 'REFERENCES', 'TRIGGER');
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: runtime role holds an excessive privilege: %', offenders;
  END IF;

  -- ----------------------------------------------------------------------------------------------
  -- 6. PUBLIC has no rights in the app schema.
  -- ----------------------------------------------------------------------------------------------
  SELECT count(*) INTO n
  FROM information_schema.table_privileges
  WHERE table_schema = 'app' AND grantee = 'PUBLIC';
  IF n > 0 THEN
    RAISE EXCEPTION 'FAIL: PUBLIC holds % privilege(s) in schema app', n;
  END IF;

  RAISE NOTICE 'PASS: permission and RLS smoke tests';
END
$$;

-- ------------------------------------------------------------------------------------------------
-- 7. Tenant isolation, exercised as the API role itself (V-04, T-006).
-- ------------------------------------------------------------------------------------------------
SET ROLE sp_api_role;

DO $$
DECLARE
  visible integer;
BEGIN
  -- No request context: nothing is visible.
  SELECT count(*) INTO visible FROM app.orders;
  IF visible <> 0 THEN
    RAISE EXCEPTION 'FAIL: % order row(s) visible without request context', visible;
  END IF;

  -- Cedar context: only cedar rows.
  PERFORM set_config('app.organization_id', '11111111-1111-1111-1111-111111111111', true);
  PERFORM set_config('app.user_id', 'a1111111-1111-1111-1111-111111111111', true);

  SELECT count(*) INTO visible
  FROM app.orders
  WHERE organization_id <> '11111111-1111-1111-1111-111111111111';
  IF visible <> 0 THEN
    RAISE EXCEPTION 'FAIL: % foreign-tenant order row(s) visible under cedar context', visible;
  END IF;

  -- The northwind order is invisible by number, which is the cross-tenant read attempt (T-002).
  SELECT count(*) INTO visible FROM app.orders WHERE order_number = 'ORD-3001';
  IF visible <> 0 THEN
    RAISE EXCEPTION 'FAIL: ORD-3001 visible under cedar context';
  END IF;

  RAISE NOTICE 'PASS: tenant isolation under sp_api_role';
END
$$;

RESET ROLE;

-- ==================================================================================================
-- The Range (0010).
--
-- The Range can arm controls into broken states, which is the largest piece of authority in this
-- repository. These assertions are what keeps it from quietly becoming a second superuser: if a
-- later change grants it a table, an attribute, or ownership, the migration job fails here rather
-- than the Range failing in front of a learner.
-- ==================================================================================================
DO $$
DECLARE
  offenders text;
  n integer;
BEGIN
  -- 1. Same dangerous-attribute rule as every other runtime role.
  SELECT string_agg(rolname, ', ') INTO offenders
  FROM pg_roles
  WHERE rolname = 'sp_range_role'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: sp_range_role holds a dangerous attribute';
  END IF;

  -- 2. It owns nothing, anywhere.
  SELECT count(*) INTO n
  FROM pg_class c
  WHERE pg_get_userbyid(c.relowner) = 'sp_range_role';
  IF n <> 0 THEN
    RAISE EXCEPTION 'FAIL: sp_range_role owns % relation(s)', n;
  END IF;

  SELECT count(*) INTO n
  FROM pg_namespace WHERE pg_get_userbyid(nspowner) = 'sp_range_role';
  IF n <> 0 THEN
    RAISE EXCEPTION 'FAIL: sp_range_role owns % schema(s)', n;
  END IF;

  -- 3. It holds no privilege on any table in app. This is the assertion that matters most: the
  --    Range reads another tenant's rows through a SECURITY DEFINER function or not at all, so a
  --    direct grant here would silently replace a reviewed function with an open door.
  SELECT string_agg(table_name || ':' || privilege_type, ', ') INTO offenders
  FROM information_schema.table_privileges
  WHERE grantee = 'sp_range_role' AND table_schema = 'app';
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: sp_range_role holds privileges on app tables: %', offenders;
  END IF;

  -- 4. It cannot create in the range schema; it may only enter it and call what it was granted.
  IF has_schema_privilege('sp_range_role', 'range', 'CREATE') THEN
    RAISE EXCEPTION 'FAIL: sp_range_role may CREATE in schema range';
  END IF;
  IF NOT has_schema_privilege('sp_range_role', 'range', 'USAGE') THEN
    RAISE EXCEPTION 'FAIL: sp_range_role cannot USAGE schema range';
  END IF;

  -- 5. Every function it can call is SECURITY DEFINER and owned by the migration role. A function
  --    that is neither runs with the Range's own rights, which would make it useless and hide the
  --    fact that it is useless behind an empty result.
  SELECT string_agg(p.proname, ', ') INTO offenders
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'range'
    AND has_function_privilege('sp_range_role', p.oid, 'EXECUTE')
    AND (NOT p.prosecdef OR pg_get_userbyid(p.proowner) <> 'sp_migrator_role');
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: range function(s) not SECURITY DEFINER owned by the migrator: %', offenders;
  END IF;

  RAISE NOTICE 'PASS: sp_range_role is bounded to EXECUTE on reviewed functions';
END
$$;
