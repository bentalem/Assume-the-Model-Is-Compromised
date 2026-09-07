-- 0001 — Roles, schema, and context helpers.
--
-- Run by the bootstrap superuser (once). Everything afterwards is owned by sp_migrator_role.
-- Runtime roles own nothing and hold no bypass privilege (SP-DATA-001 §5).

BEGIN;

-- ------------------------------------------------------------------------------------------------
-- Roles. Passwords are injected by the migration entrypoint from mounted secret files.
--
-- These use psql variable substitution with \gexec rather than a DO block: psql does not substitute
-- variables inside dollar-quoted bodies, so a DO block would receive the literal text ":'password'".
-- format(%L) quotes the value for SQL, and the password never appears in a committed file.
-- ------------------------------------------------------------------------------------------------
SELECT format('CREATE ROLE sp_migrator_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'migrator_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_migrator_role')
\gexec

SELECT format('CREATE ROLE sp_api_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'api_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_api_role')
\gexec

SELECT format('CREATE ROLE sp_worker_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'worker_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_worker_role')
\gexec

SELECT format('CREATE ROLE sp_auditor_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'auditor_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_auditor_role')
\gexec

-- Belt and braces: if a role already existed, force the safe attributes.
ALTER ROLE sp_api_role     NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE sp_worker_role  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE sp_auditor_role NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE sp_migrator_role NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- ------------------------------------------------------------------------------------------------
-- Schema. The migration role owns it, so runtime roles cannot bypass row policies via ownership.
-- ------------------------------------------------------------------------------------------------
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION sp_migrator_role;

GRANT USAGE ON SCHEMA app TO sp_api_role, sp_worker_role, sp_auditor_role;

-- No blanket privileges on future objects. Every grant is written out per table.
ALTER DEFAULT PRIVILEGES FOR ROLE sp_migrator_role IN SCHEMA app
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE sp_migrator_role IN SCHEMA app
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE sp_migrator_role IN SCHEMA app
  REVOKE ALL ON FUNCTIONS FROM PUBLIC;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------------------------------------------
-- Request context helpers.
--
-- Both return NULL when the setting is absent, so every policy USING clause evaluates to NULL
-- (not true) and no rows are visible. This is what makes check V-04 return zero rows rather than
-- relying on the application always remembering to filter.
-- ------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.current_org() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('app.organization_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

ALTER FUNCTION app.current_org()     OWNER TO sp_migrator_role;
ALTER FUNCTION app.current_user_id() OWNER TO sp_migrator_role;

GRANT EXECUTE ON FUNCTION app.current_org(), app.current_user_id()
  TO sp_api_role, sp_worker_role, sp_auditor_role;

-- ------------------------------------------------------------------------------------------------
-- Schema version tracking.
-- ------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.schema_migrations (
  version     text PRIMARY KEY,
  applied_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.schema_migrations OWNER TO sp_migrator_role;

COMMIT;
