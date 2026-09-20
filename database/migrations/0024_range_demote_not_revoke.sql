-- 0024 — Challenge 1.3 demoted the wrong thing.
--
-- 0023 revoked bob's support_manager membership. It is his only membership, so revoking it removed
-- him from the tenant entirely and the next request came back 404 — refused by the resource lookup
-- before policy was ever consulted.
--
-- That is a true and interesting outcome, and it is not the one the challenge teaches. The lesson
-- is "roles are read from the server on every request", and the sharpest way to see it is a request
-- that still succeeds while returning *less*: the field set narrows, mid-session, with the same
-- token. A 404 shows something changed; a narrowed field list shows exactly what.
--
-- So the mutation demotes rather than revokes. bob stays in the tenant, keeps a role, and stops
-- being a manager.
--
-- Worth recording how it was found: the challenge content was written before the mutation was run
-- end to end, and asserted that `email` would stop coming back while the request still succeeded.
-- Running it produced a 404 instead. The content was wrong, not the system — and content that
-- describes an outcome nobody has observed is the same class of error as a test named for a claim
-- it does not check.

BEGIN;

SET ROLE sp_migrator_role;

CREATE OR REPLACE FUNCTION range.arm_revoke_bob_manager() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  UPDATE app.memberships m
  SET role = 'support_agent'
  WHERE m.role = 'support_manager' AND m.status = 'active';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed = 0 THEN
    RAISE EXCEPTION 'no active support_manager membership to demote';
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION range.restore_bob_manager() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  -- Restores the one person the lab seeds as a manager. Matching on the display name here rather
  -- than on the role, because after the demotion there is no support_manager row to find.
  UPDATE app.memberships m
  SET role = 'support_manager'
  FROM app.users u
  WHERE u.id = m.user_id
    AND u.display_name = 'Bob Ferreira'
    AND m.role <> 'support_manager';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed = 0 THEN
    RAISE EXCEPTION 'no demoted membership to restore';
  END IF;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0024_range_demote_not_revoke');

RESET ROLE;
COMMIT;
