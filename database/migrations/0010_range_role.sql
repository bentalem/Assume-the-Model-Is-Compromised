-- 0010 — The Range: a fifth role, and the only surface it is allowed to touch.
--
-- The Range arms controls into broken states so a learner can watch the consequence. That is more
-- authority than anything else in this system holds, and a service that can drop FORCE on a table
-- is exactly the control-plane violation the lab teaches people to find. So it gets none of that
-- authority directly.
--
-- `sp_range_role` owns nothing, reads no table in `app`, and holds no privilege beyond EXECUTE on a
-- fixed set of functions in the `range` schema. Every one of those functions is owned by
-- sp_migrator_role and marked SECURITY DEFINER, so the reach of the whole service is the list of
-- functions in this file — auditable in one place, and changed only by a reviewed migration.
--
-- Two consequences worth stating, because they are the design rather than an accident:
--
--   * A result panel that shows another tenant's rows works because the function runs as the table
--     owner, not because the Range can read across tenants. Revoke EXECUTE and the Range is blind.
--   * Nothing here grants CREATE, and nothing grants ALTER. Arming a control is a call to a named
--     function that performs one specific change, never a statement the service composes.

BEGIN;

-- ------------------------------------------------------------------------------------------------
-- The role.
--
-- Created the same way as the four in 0001: psql variable substitution with \gexec, because psql
-- does not substitute inside dollar-quoted bodies. The password comes from a mounted secret file
-- and never appears in a committed file.
-- ------------------------------------------------------------------------------------------------
SELECT format('CREATE ROLE sp_range_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'range_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_range_role')
\gexec

-- Belt and braces, exactly as 0001 does: if the role already existed, force the safe attributes.
ALTER ROLE sp_range_role NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- ------------------------------------------------------------------------------------------------
-- The schema. Created by the bootstrap superuser and handed to the migration role, exactly as 0001
-- does for `app`: sp_migrator_role is NOCREATEDB and holds no CREATE on the database, which is the
-- attribute that stops a migration credential from becoming a general-purpose one.
--
-- Owned by the migration role; the Range may enter it but may not create in it.
-- ------------------------------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS range AUTHORIZATION sp_migrator_role;

REVOKE ALL ON SCHEMA range FROM PUBLIC;
GRANT USAGE ON SCHEMA range TO sp_range_role;

SET ROLE sp_migrator_role;

-- No default privileges for this schema. Every function is granted by name, below, so adding a
-- function does not silently widen what the Range can call.

-- ------------------------------------------------------------------------------------------------
-- The audit trail gains a third actor type.
--
-- Everything the Range does is written here. A learner working challenge 7.1 goes looking for a
-- request in the trail and finds their own arming next to it, attributed and timestamped. That is
-- deliberate: the service with the most authority in the repository is also the one whose actions
-- are hardest to miss.
-- ------------------------------------------------------------------------------------------------
ALTER TABLE app.audit_events DROP CONSTRAINT audit_events_actor_type_check;
ALTER TABLE app.audit_events ADD  CONSTRAINT audit_events_actor_type_check
  CHECK (actor_type IN ('user', 'workload', 'range'));

-- ------------------------------------------------------------------------------------------------
-- range.record_event — the only way the Range writes anything.
--
-- SECURITY DEFINER because FORCE row security applies to the table owner too, so even
-- sp_migrator_role needs a policy to insert. Rather than granting the Range INSERT and adding a
-- policy for it, the write goes through here: the Range cannot choose the actor type, cannot
-- forge a decision value the constraint would reject, and cannot write a row that does not name a
-- mutation.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY audit_migrator_insert ON app.audit_events FOR INSERT TO sp_migrator_role
WITH CHECK (true);

CREATE FUNCTION range.record_event(
  p_request_id  text,
  p_action      text,
  p_mutation_id text,
  p_decision    text,
  p_reason      text
) RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  INSERT INTO app.audit_events (request_id, actor_type, actor_id, action,
                                resource_type, resource_id, decision, reason)
  VALUES (p_request_id, 'range', 'range-service', p_action,
          'mutation', p_mutation_id, p_decision, p_reason);
$$;

ALTER FUNCTION range.record_event(text, text, text, text, text) OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.record_event(text, text, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.record_event(text, text, text, text, text) TO sp_range_role;

-- ------------------------------------------------------------------------------------------------
-- range.table_security — the probe behind every row-security mutation.
--
-- Reads the catalogue rather than remembering what the Range believes it did. A learner who arms
-- something outside the Range, or restores a container, sees the truth on the next page load.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.table_security(p_table text)
RETURNS TABLE (table_name text, owner text, rls_enabled boolean, rls_forced boolean)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
  SELECT c.relname::text,
         pg_get_userbyid(c.relowner)::text,
         c.relrowsecurity,
         c.relforcerowsecurity
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app'
    AND c.relkind = 'r'
    AND c.relname = p_table;
$$;

ALTER FUNCTION range.table_security(text) OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.table_security(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.table_security(text) TO sp_range_role;

-- ------------------------------------------------------------------------------------------------
-- range.all_table_security — the catalogue query challenge 2.3 hands the learner.
--
-- The same four facts for every table in `app`: which role owns it, whether row security is
-- enabled, and whether it is forced. This is the query worth carrying into somebody else's review,
-- so the Range shows it rather than describing it.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.all_table_security()
RETURNS TABLE (table_name text, owner text, rls_enabled boolean, rls_forced boolean)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
  SELECT c.relname::text,
         pg_get_userbyid(c.relowner)::text,
         c.relrowsecurity,
         c.relforcerowsecurity
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app' AND c.relkind = 'r'
  ORDER BY c.relname;
$$;

ALTER FUNCTION range.all_table_security() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.all_table_security() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.all_table_security() TO sp_range_role;

-- ------------------------------------------------------------------------------------------------
-- range.role_attributes — the other half of the four questions.
--
-- Superuser and BYPASSRLS on the roles that matter. A learner auditing a system that looks correct
-- needs both halves; neither one alone answers "is this table actually filtering".
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.role_attributes()
RETURNS TABLE (role_name text, is_superuser boolean, bypasses_rls boolean)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
  SELECT rolname::text, rolsuper, rolbypassrls
  FROM pg_roles
  WHERE rolname LIKE 'sp\_%\_role'
  ORDER BY rolname;
$$;

ALTER FUNCTION range.role_attributes() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.role_attributes() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.role_attributes() TO sp_range_role;

INSERT INTO app.schema_migrations (version) VALUES ('0010_range_role');

RESET ROLE;
COMMIT;
