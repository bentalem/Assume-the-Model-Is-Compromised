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
