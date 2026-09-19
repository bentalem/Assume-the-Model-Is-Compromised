-- 0017 — The Range: challenge 6.2, separation of duty.
--
-- These observations *attempt* a write and report what refused them. Nothing is left behind: each
-- one runs its insert inside an exception block, so the failure rolls back the sub-transaction and
-- the successful case is undone explicitly.
--
-- That is worth being deliberate about. An observation that can write is a different kind of thing
-- from one that reads, and the reason it is acceptable here is that the *point* of the challenge is
-- what happens when the write is refused. The safeguards:
--
--   * Neither function takes an argument. They act on one seeded action request, named in the body.
--   * Both report the database's own error text rather than interpreting it, so a learner sees the
--     refusal rather than this file's opinion of it.
--   * The permitted case is rolled back by hand, because a challenge that silently approves a
--     refund the first time somebody presses Run is not a teaching tool.

BEGIN;

SET ROLE sp_migrator_role;

-- ------------------------------------------------------------------------------------------------
-- range.attempt_self_approval — alice approving alice's own refund request.
--
-- The trigger in 0008 is the third of three independent refusals: policy refuses it, the approval
-- portal refuses it, and this refuses it even if both of those are bypassed entirely. A learner who
-- has only seen the first two has seen a control that one mistake could remove.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.attempt_self_approval()
RETURNS TABLE (attempt text, outcome text, refused_by text, detail text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
DECLARE
  target      uuid;
  requester   uuid;
  target_hash text;
BEGIN
  SELECT r.id, r.requester_id, r.payload_hash
    INTO target, requester, target_hash
  FROM app.action_requests r
  WHERE r.state = 'PENDING_APPROVAL'
  ORDER BY r.created_at DESC
  LIMIT 1;

  IF target IS NULL THEN
    RETURN QUERY SELECT
      'self-approval'::text,
      'no pending request to attempt'::text,
      '-'::text,
      'propose a refund first — challenge 6.2 needs something awaiting approval'::text;
    RETURN;
  END IF;

  BEGIN
    INSERT INTO app.approval_decisions
      (action_request_id, approver_id, decision, approved_hash, comment, policy_version)
    VALUES (target, requester, 'approved', target_hash, 'range: 6.2 attempt', '2026-09-07.1');

    -- Reached only if every control failed. Undo it and say so loudly.
    DELETE FROM app.approval_decisions
    WHERE action_request_id = target AND comment = 'range: 6.2 attempt';

    RETURN QUERY SELECT
      'self-approval'::text,
      'ACCEPTED — and rolled back by the Range'::text,
      'nothing'::text,
      'the requester approved their own action; separation of duty is not enforced here'::text;
  EXCEPTION WHEN others THEN
    RETURN QUERY SELECT
      'self-approval'::text,
      'refused'::text,
      'database trigger'::text,
      SQLERRM::text;
  END;
END
$$;

-- ------------------------------------------------------------------------------------------------
-- range.attempt_independent_approval — the control group.
--
-- The same insert with a different approver. It must succeed, and is then removed. Without this a
-- learner cannot tell a working separation-of-duty control from a table that refuses every insert.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.attempt_independent_approval()
RETURNS TABLE (attempt text, outcome text, refused_by text, detail text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
DECLARE
  target      uuid;
  requester   uuid;
  approver    uuid;
  target_hash text;
BEGIN
  SELECT r.id, r.requester_id, r.payload_hash
    INTO target, requester, target_hash
  FROM app.action_requests r
  WHERE r.state = 'PENDING_APPROVAL'
  ORDER BY r.created_at DESC
  LIMIT 1;

  IF target IS NULL THEN
    RETURN QUERY SELECT
      'independent approval'::text, 'no pending request to attempt'::text, '-'::text, ''::text;
    RETURN;
  END IF;

  SELECT u.id INTO approver FROM app.users u WHERE u.id <> requester LIMIT 1;

  BEGIN
    INSERT INTO app.approval_decisions
      (action_request_id, approver_id, decision, approved_hash, comment, policy_version)
    VALUES (target, approver, 'approved', target_hash, 'range: 6.2 control', '2026-09-07.1');

    DELETE FROM app.approval_decisions
    WHERE action_request_id = target AND comment = 'range: 6.2 control';

    RETURN QUERY SELECT
      'independent approval'::text,
      'accepted, then rolled back'::text,
      'nothing'::text,
      'a different approver is permitted — so the refusal above is about who, not about the row'::text;
  EXCEPTION WHEN others THEN
    RETURN QUERY SELECT
      'independent approval'::text, 'refused'::text, 'database'::text, SQLERRM::text;
  END;
END
$$;

-- ------------------------------------------------------------------------------------------------
-- range.pending_actions — what is waiting, so the learner can see there is something to approve.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.pending_actions()
RETURNS TABLE (action_id text, action_type text, resource text, state text, risk text, payload_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT left(r.id::text, 8) || '…',
         r.action_type,
         coalesce(r.resource_id, '-'),
         r.state,
         r.risk_level,
         left(r.payload_hash, 16) || '…'
  FROM app.action_requests r
  ORDER BY r.created_at DESC
  LIMIT 10;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.attempt_self_approval()',
    'range.attempt_independent_approval()',
    'range.pending_actions()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

-- The migration role writes to approval_decisions only through the functions above, and FORCE row
-- security applies to it like everyone else, so it needs policies of its own. Insert and delete
-- rather than update: these functions add a row and remove the same row, and nothing here should be
-- able to amend an approval that was genuinely recorded.
CREATE POLICY approvals_migrator_read   ON app.approval_decisions FOR SELECT TO sp_migrator_role USING (true);
CREATE POLICY approvals_migrator_insert ON app.approval_decisions FOR INSERT TO sp_migrator_role WITH CHECK (true);
CREATE POLICY approvals_migrator_delete ON app.approval_decisions FOR DELETE TO sp_migrator_role
  USING (comment IN ('range: 6.2 attempt', 'range: 6.2 control'));

CREATE POLICY actions_migrator_read ON app.action_requests FOR SELECT TO sp_migrator_role USING (true);

INSERT INTO app.schema_migrations (version) VALUES ('0017_range_separation_of_duty');

RESET ROLE;
COMMIT;
