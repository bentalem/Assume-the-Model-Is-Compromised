-- 0001 — memory-db foundation: request context, the armable settings, and the audit trail.
--
-- memory-db is its own PostgreSQL instance, and it keeps the core's discipline exactly:
--
--   * A migration role (`mem_migrator`) owns every schema object. Runtime roles own nothing and
--     hold no BYPASSRLS, so row-level security applies to them without exception.
--   * Every table has row-level security ENABLED and FORCED — FORCE, so that even the owning role
--     is subject to it and a SECURITY DEFINER function must be given a policy of its own to read.
--   * Request context is transaction-local. The service sets it with set_config(..., true) in the
--     same transaction as the query, never with a session-level SET. Challenge 2.2 is about what
--     happens otherwise, and it applies here unchanged.
--
-- Roles and schemas are created by memory-init before this file runs (it needs their passwords,
-- which never appear in a committed file). This file runs with `SET ROLE mem_migrator`.

SET ROLE mem_migrator;

-- ------------------------------------------------------------------------------------------------
-- Request context.
--
-- Each reads a transaction-local setting and turns an empty or missing value into NULL. NULL is
-- the fail-closed value: every policy below compares against these, and a comparison with NULL is
-- never true, so a query run with no context established sees nothing.
--
-- `mem.roles()` is a list, not a single role, because a person can hold more than one membership
-- in an organisation. The design brief says `mem.role`; a list is what the core database already
-- uses (`app.roles`) and what is true of the data.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION mem.user_sub() RETURNS text
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('mem.user_sub', true), '') $$;

CREATE FUNCTION mem.org_id() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('mem.org_id', true), '')::uuid $$;

CREATE FUNCTION mem.roles() RETURNS text[]
LANGUAGE sql STABLE
AS $$
  SELECT CASE
    WHEN nullif(current_setting('mem.roles', true), '') IS NULL THEN ARRAY[]::text[]
    ELSE string_to_array(current_setting('mem.roles', true), ',')
  END
$$;

CREATE FUNCTION mem.has_role(p_role text) RETURNS boolean
LANGUAGE sql STABLE
AS $$ SELECT p_role = ANY (mem.roles()) $$;

-- ------------------------------------------------------------------------------------------------
-- The armable settings.
--
-- Eight rows, one per Range mutation in track 9. Each is a configuration a real deployment might
-- legitimately ship — auto-saving memories, one shared vector collection, managers reading
-- transcripts for quality review — and never a code path that exists only to be wrong. The policies
-- and the service read these per request; arming one flips a row and needs no restart.
--
-- The key is checked against a fixed list, so nothing can create a setting the code does not know
-- about, and the service's role holds no write on this table at all: it cannot arm itself. Only
-- range_mem.set_setting can, and that writes audit evidence in the same transaction.
-- ------------------------------------------------------------------------------------------------
CREATE TABLE mem.settings (
  key        text PRIMARY KEY CHECK (key IN (
               'write.secret_filter',
               'context.provenance',
               'history.org_readable',
               'history.revalidate',
               'write.auto_confirm',
               'store.layout',
               'rules.self_activate',
               'forget.scope'
             )),
  value      text NOT NULL,
  changed_at timestamptz NOT NULL DEFAULT now()
);

-- The secure value of every setting. Reset asserts these; the Range's probes compare against them.
INSERT INTO mem.settings (key, value) VALUES
  ('write.secret_filter',  'on'),
  ('context.provenance',   'on'),
  ('history.org_readable', 'false'),
  ('history.revalidate',   'on'),
  ('write.auto_confirm',   'false'),
  ('store.layout',         'per_tenant'),
  ('rules.self_activate',  'false'),
  ('forget.scope',         'all');

ALTER TABLE mem.settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.settings FORCE  ROW LEVEL SECURITY;

-- The owner may read settings so that mem.setting(), which runs as the owner, can answer. FORCE
-- applies to the owner too; without this policy the function would see no rows and every setting
-- would read as NULL — which the callers below treat as the secure value, so it would fail closed,
-- but silently, and a learner arming a control would watch nothing happen.
CREATE POLICY settings_owner_read ON mem.settings FOR SELECT TO mem_migrator USING (true);

-- A setting's value, read with the owner's rights. The only route the service and the policies have
-- to this table.
CREATE FUNCTION mem.setting(p_key text) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, pg_temp
AS $$ SELECT value FROM mem.settings WHERE key = p_key $$;

-- ------------------------------------------------------------------------------------------------
-- The audit trail. Append-only: the service may INSERT and nothing else, so a record of what the
-- memory layer did cannot be edited by the memory layer.
-- ------------------------------------------------------------------------------------------------
CREATE TABLE mem.audit_events (
  event_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at   timestamptz NOT NULL DEFAULT now(),
  request_id    text NOT NULL,
  actor_type    text NOT NULL CHECK (actor_type IN ('user', 'runtime', 'range')),
  actor_sub     text,
  org_id        uuid,
  action        text NOT NULL,
  resource_type text,
  resource_id   text,
  decision      text NOT NULL CHECK (decision IN ('allowed', 'denied', 'succeeded', 'failed')),
  reason        text NOT NULL
);

CREATE INDEX audit_request ON mem.audit_events (request_id);
CREATE INDEX audit_org_time ON mem.audit_events (org_id, occurred_at DESC);

ALTER TABLE mem.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.audit_events FORCE  ROW LEVEL SECURITY;

-- The service may record events for the organisation it is acting in, or with no organisation (a
-- refusal that happened before a tenant was known).
CREATE POLICY audit_service_insert ON mem.audit_events FOR INSERT TO mem_service_role
WITH CHECK (org_id IS NULL OR org_id = mem.org_id());

-- The owner reads the trail, so the Range's observations (SECURITY DEFINER, owned by this role)
-- can show it. SELECT only: an investigator's tool that could edit the record would not be one.
CREATE POLICY audit_owner_read ON mem.audit_events FOR SELECT TO mem_migrator USING (true);

-- The Range writes its own arming here, through range_mem.set_setting, as the owner.
CREATE POLICY audit_owner_insert ON mem.audit_events FOR INSERT TO mem_migrator WITH CHECK (true);

GRANT INSERT ON mem.audit_events TO mem_service_role;

-- ------------------------------------------------------------------------------------------------
-- Function grants. PostgreSQL grants EXECUTE to PUBLIC on every new function; revoke it and grant
-- by name, so the list of callable functions is the list in these files.
-- ------------------------------------------------------------------------------------------------
REVOKE ALL ON FUNCTION mem.user_sub()     FROM PUBLIC;
REVOKE ALL ON FUNCTION mem.org_id()       FROM PUBLIC;
REVOKE ALL ON FUNCTION mem.roles()        FROM PUBLIC;
REVOKE ALL ON FUNCTION mem.has_role(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION mem.setting(text)  FROM PUBLIC;

GRANT EXECUTE ON FUNCTION mem.user_sub()     TO mem_service_role;
GRANT EXECUTE ON FUNCTION mem.org_id()       TO mem_service_role;
GRANT EXECUTE ON FUNCTION mem.roles()        TO mem_service_role;
GRANT EXECUTE ON FUNCTION mem.has_role(text) TO mem_service_role;
GRANT EXECUTE ON FUNCTION mem.setting(text)  TO mem_service_role;

RESET ROLE;
