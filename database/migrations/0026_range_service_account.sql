-- 0026 — The Range: challenge 1.1, the service account.
--
-- The realm declares a user `agent-service` with the fixed subject `agent-service-id`. This seeds
-- the matching row in app.users so the API can resolve that subject, and gives the Range a mutation
-- that grants it membership in *both* tenants — which is what a service account is.
--
-- The user exists with no memberships by default. That matters: unarmed, the account authenticates
-- perfectly and can reach nothing, so the challenge's flag is unobtainable before anything is
-- armed, and the account sitting in the realm is not a standing hole in the lab.
--
-- `scripts/learn_service_account.py` builds the same fixture at runtime through the Keycloak admin
-- API. The declarative version is better for the same reason as 1.2's `another-service`: a fixture
-- a script conjures with admin credentials is control-plane mutation, and the same fixture in the
-- realm import plus a migration is configuration somebody reviewed.

BEGIN;

-- Fixed id, matching the realm's fixed subject. A realm import honours a supplied id; the admin API
-- does not, which is why the script has to discover the generated one afterwards and this does not.
--
-- Seeded as the bootstrap superuser, before SET ROLE. app.users has FORCE row security and the
-- migration role holds only a read policy on it — deliberately, from 0002. Adding an insert policy
-- so that one seed row could be written would widen what the migration role can do to the identity
-- table permanently, to save one line here.
INSERT INTO app.users (id, identity_subject, display_name)
VALUES ('5e111111-1111-1111-1111-111111111111', 'agent-service-id', 'SupportPilot Agent (service)')
ON CONFLICT (id) DO UPDATE SET identity_subject = EXCLUDED.identity_subject;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.arm_service_account() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer := 0;
  n       integer;
BEGIN
  -- Membership in every tenant, with the widest read role in each. That breadth is not carelessness
  -- and it is not a mistake in the fixture: one credential that answers for every user must reach
  -- everything any of them could. There is no narrower version of a service account.
  FOR n IN
    INSERT INTO app.memberships (user_id, organization_id, role, status)
    SELECT '5e111111-1111-1111-1111-111111111111', o.id, 'support_manager', 'active'
    FROM app.organizations o
    ON CONFLICT (user_id, organization_id, role) DO UPDATE SET status = 'active'
    RETURNING 1
  LOOP
    changed := changed + 1;
  END LOOP;

  IF changed = 0 THEN
    RAISE EXCEPTION 'no organizations to grant the service account membership in';
  END IF;
END
$$;

CREATE FUNCTION range.restore_service_account() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  DELETE FROM app.memberships
  WHERE user_id = '5e111111-1111-1111-1111-111111111111';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed = 0 THEN
    RAISE EXCEPTION 'the service account already holds no memberships';
  END IF;
END
$$;

CREATE FUNCTION range.service_account_reach()
RETURNS TABLE (account text, tenant text, role text, status text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT u.display_name, o.slug, m.role, m.status
  FROM app.users u
  LEFT JOIN app.memberships m ON m.user_id = u.id
  LEFT JOIN app.organizations o ON o.id = m.organization_id
  WHERE u.id = '5e111111-1111-1111-1111-111111111111'
  ORDER BY o.slug;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_service_account()',
    'range.restore_service_account()',
    'range.service_account_reach()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

-- The mutation inserts and deletes memberships, so the migration role needs both. Scoped by the
-- policies' own WHERE clauses to this one account: nothing here should be able to grant a tenant to
-- a real person, which would be a change to who can see what rather than a demonstration of it.
CREATE POLICY memberships_migrator_insert ON app.memberships FOR INSERT TO sp_migrator_role
WITH CHECK (user_id = '5e111111-1111-1111-1111-111111111111');
CREATE POLICY memberships_migrator_delete ON app.memberships FOR DELETE TO sp_migrator_role
USING (user_id = '5e111111-1111-1111-1111-111111111111');

INSERT INTO app.schema_migrations (version) VALUES ('0026_range_service_account');

RESET ROLE;
COMMIT;
