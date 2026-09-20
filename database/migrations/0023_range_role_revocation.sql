-- 0023 — The Range: challenge 1.3, roles come from the database.
--
-- Revoke bob's manager membership while his token keeps working, then make the same request again.
-- The token does not change. The answer does — because the token was never what decided.
--
-- `status` rather than DELETE. A membership row carries `granted_at` and a status, and the lab's
-- own model is that access is revoked rather than erased: deleting the row would lose the fact that
-- it once existed, which is the thing an investigator needs six months later. The restore sets it
-- back to 'active', so the round trip is a state change rather than a re-grant.

BEGIN;

SET ROLE sp_migrator_role;

-- Both of these raise if they change nothing.
--
-- The first draft matched on a display name that does not exist in the seeds. The UPDATE succeeded,
-- affected zero rows, and the function returned normally — so arming would have appeared to work
-- while changing nothing, and the probe would have gone on reporting `correct` forever. A mutation
-- that can succeed without doing anything is worse than one that fails, because the console would
-- have been lying rather than broken.
CREATE FUNCTION range.arm_revoke_bob_manager() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  UPDATE app.memberships m
  SET status = 'revoked'
  FROM app.users u
  WHERE u.id = m.user_id
    AND m.role = 'support_manager'
    AND m.status = 'active';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed = 0 THEN
    RAISE EXCEPTION 'no active support_manager membership to revoke';
  END IF;
END
$$;

CREATE FUNCTION range.restore_bob_manager() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  UPDATE app.memberships m
  SET status = 'active'
  FROM app.users u
  WHERE u.id = m.user_id
    AND m.role = 'support_manager'
    AND m.status <> 'active';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed = 0 THEN
    RAISE EXCEPTION 'no revoked support_manager membership to restore';
  END IF;
END
$$;

-- What the server believes about a person, which is the only thing that decides anything.
CREATE FUNCTION range.memberships_for_lab_users()
RETURNS TABLE (person text, role text, status text, granted text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT u.display_name, m.role, m.status, to_char(m.granted_at, 'YYYY-MM-DD')
  FROM app.memberships m
  JOIN app.users u ON u.id = m.user_id
  ORDER BY u.display_name, m.role;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_revoke_bob_manager()',
    'range.restore_bob_manager()',
    'range.memberships_for_lab_users()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

-- FORCE row security applies to the owner, so the migration role needs its own policies here. It
-- already has read on users and memberships from 0002 (added so app.resolve_subject could see past
-- its own table's FORCE); this adds the update the mutation needs, scoped to the status column's
-- table and to nothing else.
CREATE POLICY memberships_migrator_update ON app.memberships FOR UPDATE TO sp_migrator_role
USING (true) WITH CHECK (true);

INSERT INTO app.schema_migrations (version) VALUES ('0023_range_role_revocation');

RESET ROLE;
COMMIT;
