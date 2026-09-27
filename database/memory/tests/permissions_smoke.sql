-- memory-db permission and row-security smoke tests.
--
-- Run by memory-init after migrations, on every start. Any failure raises, which fails the job,
-- which stops the memory service from starting — the same arrangement as the core database, where a
-- regression in these properties is a failed deployment rather than a warning in a log.

-- ------------------------------------------------------------------------------------------------
-- 1. Runtime roles: no elevated attribute, no ownership of anything.
-- ------------------------------------------------------------------------------------------------
DO $$
DECLARE
  r text;
  n integer;
BEGIN
  FOREACH r IN ARRAY ARRAY['mem_service_role', 'mem_range_role'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      RAISE EXCEPTION 'FAIL: role % does not exist', r;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r
               AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)) THEN
      RAISE EXCEPTION 'FAIL: % holds an elevated attribute', r;
    END IF;
    SELECT count(*) INTO n FROM pg_class WHERE pg_get_userbyid(relowner) = r;
    IF n <> 0 THEN
      RAISE EXCEPTION 'FAIL: % owns % relation(s)', r, n;
    END IF;
    SELECT count(*) INTO n FROM pg_namespace WHERE pg_get_userbyid(nspowner) = r;
    IF n <> 0 THEN
      RAISE EXCEPTION 'FAIL: % owns % schema(s)', r, n;
    END IF;
    IF has_schema_privilege(r, 'mem', 'CREATE') OR has_schema_privilege(r, 'range_mem', 'CREATE') THEN
      RAISE EXCEPTION 'FAIL: % may CREATE in a memory schema', r;
    END IF;
  END LOOP;
  RAISE NOTICE 'PASS: runtime roles own nothing and hold no elevated attribute';
END
$$;

-- ------------------------------------------------------------------------------------------------
-- 2. Every table in `mem` has row-level security enabled AND forced.
-- ------------------------------------------------------------------------------------------------
DO $$
DECLARE
  offenders text;
BEGIN
  SELECT string_agg(c.relname, ', ') INTO offenders
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'mem' AND c.relkind = 'r'
    AND c.relname <> 'schema_migrations'
    AND NOT (c.relrowsecurity AND c.relforcerowsecurity);
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: tables without row security enabled and forced: %', offenders;
  END IF;
  RAISE NOTICE 'PASS: every mem table has row security enabled and forced';
END
$$;

-- ------------------------------------------------------------------------------------------------
-- 3. The Range: no table privilege anywhere, and every function it may call is SECURITY DEFINER
--    owned by the migration role.
-- ------------------------------------------------------------------------------------------------
DO $$
DECLARE
  offenders text;
BEGIN
  SELECT string_agg(table_schema || '.' || table_name || ':' || privilege_type, ', ') INTO offenders
  FROM information_schema.table_privileges WHERE grantee = 'mem_range_role';
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: mem_range_role holds table privileges: %', offenders;
  END IF;

  SELECT string_agg(p.proname, ', ') INTO offenders
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'range_mem'
    AND has_function_privilege('mem_range_role', p.oid, 'EXECUTE')
    AND (NOT p.prosecdef OR pg_get_userbyid(p.proowner) <> 'mem_migrator');
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: range_mem function(s) not SECURITY DEFINER owned by the migrator: %', offenders;
  END IF;

  RAISE NOTICE 'PASS: mem_range_role is bounded to EXECUTE on reviewed functions';
END
$$;

-- ------------------------------------------------------------------------------------------------
-- 4. The service cannot rewrite history, edit the audit trail, delete anything, or arm itself.
-- ------------------------------------------------------------------------------------------------
DO $$
DECLARE
  offenders text;
BEGIN
  -- Deletes are soft (a timestamp), so no runtime role needs DELETE on any table.
  SELECT string_agg(table_name, ', ') INTO offenders
  FROM information_schema.table_privileges
  WHERE grantee = 'mem_service_role' AND privilege_type IN ('DELETE', 'TRUNCATE');
  IF offenders IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may DELETE or TRUNCATE: %', offenders;
  END IF;

  IF has_table_privilege('mem_service_role', 'mem.audit_events', 'UPDATE')
     OR has_table_privilege('mem_service_role', 'mem.audit_events', 'SELECT') THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may read or update the audit trail';
  END IF;

  IF has_table_privilege('mem_service_role', 'mem.settings', 'UPDATE')
     OR has_table_privilege('mem_service_role', 'mem.settings', 'INSERT') THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may change the armable settings';
  END IF;

  -- History is append-only: a turn once written is what was said.
  IF has_table_privilege('mem_service_role', 'mem.turns', 'UPDATE') THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may rewrite history turns';
  END IF;

  -- A memory's content, and a rule's text, cannot be changed in place.
  IF has_column_privilege('mem_service_role', 'mem.records', 'content', 'UPDATE')
     OR has_column_privilege('mem_service_role', 'mem.rules', 'text', 'UPDATE') THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may rewrite a memory or a rule in place';
  END IF;

  -- Forgetting has exactly one route, mem.forget_records (0007). A direct UPDATE of deleted_at would
  -- be refused by row-level security anyway; revoking it means there is no second implementation.
  IF has_column_privilege('mem_service_role', 'mem.records', 'deleted_at', 'UPDATE') THEN
    RAISE EXCEPTION 'FAIL: mem_service_role may set deleted_at directly';
  END IF;

  RAISE NOTICE 'PASS: the service cannot rewrite, delete, edit evidence, or arm itself';
END
$$;

-- ------------------------------------------------------------------------------------------------
-- 5. Fail closed. As the service role, with no context and then with an organisation that does not
--    exist, every table is empty — whatever it actually holds.
-- ------------------------------------------------------------------------------------------------
BEGIN;
SET LOCAL ROLE mem_service_role;

DO $$
DECLARE
  t text;
  n integer;
BEGIN
  FOREACH t IN ARRAY ARRAY['sessions', 'turns', 'records', 'rules', 'context_log', 'outbox'] LOOP
    EXECUTE format('SELECT count(*) FROM mem.%I', t) INTO n;
    IF n <> 0 THEN
      RAISE EXCEPTION 'FAIL: % row(s) of mem.% visible with no request context', n, t;
    END IF;
  END LOOP;

  PERFORM set_config('mem.user_sub', 'nobody-at-all', true);
  PERFORM set_config('mem.org_id', '00000000-0000-0000-0000-000000000000', true);
  PERFORM set_config('mem.roles', 'support_manager', true);
  FOREACH t IN ARRAY ARRAY['sessions', 'turns', 'records', 'rules', 'context_log', 'outbox'] LOOP
    EXECUTE format('SELECT count(*) FROM mem.%I', t) INTO n;
    IF n <> 0 THEN
      RAISE EXCEPTION 'FAIL: % row(s) of mem.% visible to an unknown organisation', n, t;
    END IF;
  END LOOP;

  RAISE NOTICE 'PASS: with no context, or an unknown organisation, every table reads empty';
END
$$;

ROLLBACK;

-- ------------------------------------------------------------------------------------------------
-- 6. A rule's life is the transition table in 0008, and nothing else — tested as the superuser this
--    file runs as, whom no policy restrains, so what refuses here is the trigger alone. Two UPDATE
--    policies on mem.rules can be mixed (one's USING, the other's WITH CHECK); this is what makes
--    that harmless.
-- ------------------------------------------------------------------------------------------------
BEGIN;

DO $$
DECLARE
  rid uuid;
  refused boolean;
  attempt text;
BEGIN
  INSERT INTO mem.rules (org_id, text, state, proposed_by, proposed_channel, payload_hash)
  VALUES ('00000000-0000-0000-0000-000000000000', 'smoke rule', 'proposed', 'smoke-proposer',
          'agent', repeat('0', 64))
  RETURNING id INTO rid;

  FOREACH attempt IN ARRAY ARRAY[
    'UPDATE mem.rules SET state = ''active'', decided_by = ''smoke-proposer'' WHERE id = $1',
    'UPDATE mem.rules SET state = ''retired'', retired_by = ''smoke-approver'' WHERE id = $1',
    'UPDATE mem.rules SET text = ''rewritten'' WHERE id = $1'
  ] LOOP
    refused := false;
    BEGIN
      EXECUTE attempt USING rid;
    EXCEPTION WHEN raise_exception THEN
      refused := true;
    END;
    IF NOT refused THEN
      RAISE EXCEPTION 'FAIL: the rule trigger allowed: %', attempt;
    END IF;
  END LOOP;

  UPDATE mem.rules SET state = 'active', decided_by = 'smoke-approver', decided_at = now()
  WHERE id = rid;

  FOREACH attempt IN ARRAY ARRAY[
    -- the forgery: an active rule written back as active with a different approver
    'UPDATE mem.rules SET decided_by = ''smoke-forger'' WHERE id = $1',
    'UPDATE mem.rules SET state = ''retired'', retired_by = ''smoke-forger'', decided_by = ''smoke-forger'' WHERE id = $1',
    'UPDATE mem.rules SET state = ''retired'' WHERE id = $1'
  ] LOOP
    refused := false;
    BEGIN
      EXECUTE attempt USING rid;
    EXCEPTION WHEN raise_exception THEN
      refused := true;
    END;
    IF NOT refused THEN
      RAISE EXCEPTION 'FAIL: the rule trigger allowed: %', attempt;
    END IF;
  END LOOP;

  UPDATE mem.rules SET state = 'retired', retired_by = 'smoke-approver', retired_at = now()
  WHERE id = rid;

  refused := false;
  BEGIN
    UPDATE mem.rules SET state = 'active' WHERE id = rid;
  EXCEPTION WHEN raise_exception THEN
    refused := true;
  END;
  IF NOT refused THEN
    RAISE EXCEPTION 'FAIL: a retired rule came back to life';
  END IF;

  RAISE NOTICE 'PASS: a rule moves only proposed -> decided by another -> retired, approver intact';
END
$$;

ROLLBACK;
