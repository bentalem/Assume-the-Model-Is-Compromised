-- 0002 — Organizations, users, memberships.
--
-- These three tables are how tenant context is established, so they are read slightly differently
-- from business tables: the API reads memberships with app.user_id set but app.organization_id
-- still unset. See the memberships policy below.

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE app.organizations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,
  name        text NOT NULL,
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.users (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_subject  text NOT NULL UNIQUE,   -- Keycloak 'sub'
  display_name      text NOT NULL,
  status            text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.memberships (
  user_id          uuid NOT NULL REFERENCES app.users(id),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  role             text NOT NULL CHECK (role IN ('support_agent', 'support_manager',
                                                 'finance_approver', 'auditor')),
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  granted_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organization_id, role)
);

CREATE INDEX memberships_active_user ON app.memberships (user_id) WHERE status = 'active';

-- ------------------------------------------------------------------------------------------------
-- Row security
-- ------------------------------------------------------------------------------------------------
ALTER TABLE app.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.organizations FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.users         FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.memberships   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.memberships   FORCE  ROW LEVEL SECURITY;

-- An organization row is visible when it is the request's tenant, or when the caller holds an
-- active membership in it. The second arm is what lets the API resolve 'which tenants am I in'
-- before a tenant is chosen.
CREATE POLICY organizations_visible ON app.organizations FOR SELECT TO sp_api_role
USING (
  id = app.current_org()
  OR EXISTS (
    SELECT 1 FROM app.memberships m
    WHERE m.organization_id = app.organizations.id
      AND m.user_id = app.current_user_id()
      AND m.status = 'active'
  )
);

-- A caller sees only their own user row. There is no directory read.
CREATE POLICY users_self ON app.users FOR SELECT TO sp_api_role
USING (id = app.current_user_id());

-- Memberships: own rows only.
--
-- Deliberately NOT 'or organization_id = current_org()'. Widening this to the whole tenant would
-- turn the bootstrap read into a staff directory, which no tool needs. Keep it to the caller.
CREATE POLICY memberships_self ON app.memberships FOR SELECT TO sp_api_role
USING (user_id = app.current_user_id());

-- FORCE ROW LEVEL SECURITY applies to the table owner as well, which means a SECURITY DEFINER
-- function owned by sp_migrator_role is filtered by the policies above just like any other caller —
-- and with no request context yet, it would see nothing. These policies give the migration role the
-- read it needs for app.resolve_subject to work.
--
-- This is not a way into business data: sp_migrator_role has no login credential in any runtime
-- container (it exists only for the one-shot migration job), and the three tables below hold
-- identity mappings, not customer or order records.
CREATE POLICY users_migrator_read ON app.users FOR SELECT TO sp_migrator_role USING (true);
CREATE POLICY memberships_migrator_read ON app.memberships FOR SELECT TO sp_migrator_role USING (true);
CREATE POLICY organizations_migrator_read ON app.organizations FOR SELECT TO sp_migrator_role USING (true);

-- ------------------------------------------------------------------------------------------------
-- Subject resolution.
--
-- Chicken and egg: the row policies above key on app.current_user_id(), but at the start of a
-- request the server holds only the Keycloak subject string — the uuid is what it is trying to
-- discover. Widening users_self to cover that case would turn it into an unrestricted directory
-- read for any authenticated caller.
--
-- Instead, one narrow SECURITY DEFINER function performs exactly that lookup and nothing else. It
-- takes a full identity_subject (no pattern, no listing), returns one user with their active
-- memberships, and is executable only by sp_api_role. Enumeration would require already holding a
-- verified token for the subject being looked up.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION app.resolve_subject(p_identity_subject text)
RETURNS TABLE (
  user_id          uuid,
  identity_subject text,
  display_name     text,
  organization_id  uuid,
  role             text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT u.id, u.identity_subject, u.display_name, m.organization_id, m.role
  FROM app.users u
  LEFT JOIN app.memberships m
         ON m.user_id = u.id
        AND m.status = 'active'
  LEFT JOIN app.organizations o
         ON o.id = m.organization_id
        AND o.status = 'active'
  WHERE u.identity_subject = p_identity_subject
    AND u.status = 'active'
    AND (m.organization_id IS NULL OR o.id IS NOT NULL)
$$;

ALTER FUNCTION app.resolve_subject(text) OWNER TO sp_migrator_role;

-- Not executable by PUBLIC: a definer function must never be broadly callable.
REVOKE EXECUTE ON FUNCTION app.resolve_subject(text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION app.resolve_subject(text) TO sp_api_role;

-- ------------------------------------------------------------------------------------------------
-- Grants. Column-level, no ALL.
-- ------------------------------------------------------------------------------------------------
GRANT SELECT (id, slug, name, status)                       ON app.organizations TO sp_api_role;
GRANT SELECT (id, identity_subject, display_name, status)   ON app.users         TO sp_api_role;
GRANT SELECT (user_id, organization_id, role, status)       ON app.memberships   TO sp_api_role;

INSERT INTO app.schema_migrations (version) VALUES ('0002_core_tenancy');

RESET ROLE;
COMMIT;
