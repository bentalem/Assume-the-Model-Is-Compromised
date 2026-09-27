-- 0029 — A lookup role for the memory service, and nothing else.
--
-- The memory service (track 9) needs to know, for each request, which organisation the caller
-- belongs to and which role they hold there. Roles come from this database, not from the token —
-- challenge 1.3 is about exactly why — so the memory service has to ask this database.
--
-- What it gets is the smallest thing that answers that question. Not a copy of the memberships
-- table in its own database, which would be a second source of truth for identity that drifts the
-- first time somebody is demoted. Not the API's credential, which reads every business table. One
-- login role that may do one thing: call `app.resolve_subject`, which already exists (0002), which
-- the API already uses, and whose own comment carries the security argument — it takes a full
-- identity subject, no pattern, no listing, so enumerating it needs a verified token for every
-- subject you want to enumerate.
--
-- The design brief proposed a new, parameterless function that read the subject from a
-- transaction setting instead. It was not built, because it is not stronger: the caller sets the
-- setting, so it is a parameter by another name, and it would have been a second function doing
-- the job of a reviewed one.
--
-- This is the only change the memory work makes to the core database. It is additive: no existing
-- role, grant, table or policy changes, and nothing connects as this role unless the `memory`
-- compose profile is up.

BEGIN;

-- ------------------------------------------------------------------------------------------------
-- The role. Created exactly as 0001 and 0010 create theirs: psql variable substitution with
-- \gexec, because psql does not substitute inside dollar-quoted bodies, and the password comes
-- from a mounted secret file that never appears in a committed one.
-- ------------------------------------------------------------------------------------------------
SELECT format('CREATE ROLE sp_memory_lookup_role LOGIN PASSWORD %L '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
              :'memory_lookup_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sp_memory_lookup_role')
\gexec

-- Belt and braces, exactly as 0001 and 0010 do: if the role already existed, force the safe
-- attributes rather than trusting whatever it was created with.
ALTER ROLE sp_memory_lookup_role NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- ------------------------------------------------------------------------------------------------
-- The whole of its reach: enter the schema, call one function.
--
-- USAGE on `app` lets it name the function. It confers nothing on any table in `app` — those need
-- their own grants, and there are none. `app.resolve_subject` is SECURITY DEFINER, owned by the
-- migration role, so it reads users and memberships with the owner's rights and returns one
-- subject's rows. Revoke this EXECUTE and the memory service cannot identify anyone, which is the
-- correct failure: it denies.
-- ------------------------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA app TO sp_memory_lookup_role;
GRANT EXECUTE ON FUNCTION app.resolve_subject(text) TO sp_memory_lookup_role;

INSERT INTO app.schema_migrations (version) VALUES ('0029_memory_lookup_role');

COMMIT;
