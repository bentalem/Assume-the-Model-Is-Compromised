-- 0016 — The Range: reading the audit trail, for track 7.
--
-- Track 7 is about what can be proved afterwards, so the Range needs to show the learner the trail
-- itself rather than a description of it. Two functions, both capped, both named.
--
-- A note on why the migration role needs a read policy here. app.audit_events has FORCE row
-- security and its policies name sp_api_role (insert), sp_worker_role (insert) and sp_auditor_role
-- (select). FORCE applies to the owner too, so a SECURITY DEFINER function owned by sp_migrator_role
-- reads nothing without a policy of its own — the same mechanism challenge 2.1 teaches, arriving as
-- a practical obstacle. The policy is SELECT only: the Range can read evidence and cannot amend it,
-- which matters because challenge 7.1 sends a learner into this trail to reconstruct a request and
-- an investigator's tool that can edit the record is not an investigator's tool.

BEGIN;

SET ROLE sp_migrator_role;

CREATE POLICY audit_migrator_read ON app.audit_events FOR SELECT TO sp_migrator_role
USING (true);

-- ------------------------------------------------------------------------------------------------
-- range.recent_decisions — the trail, newest first.
--
-- Deliberately shows policy_version. A denial with no version was refused before policy was ever
-- asked, and telling those two apart is the entire skill in 7.3.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.recent_decisions()
RETURNS TABLE (
  at text, actor text, action text, resource text,
  decision text, reason text, policy_version text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT to_char(e.occurred_at, 'HH24:MI:SS'),
         e.actor_type,
         e.action,
         coalesce(e.resource_id, '-'),
         e.decision,
         e.reason,
         coalesce(e.policy_version, '(none)')
  FROM app.audit_events e
  WHERE e.actor_type <> 'range'
  ORDER BY e.occurred_at DESC
  LIMIT 30;
$$;

-- ------------------------------------------------------------------------------------------------
-- range.decisions_for_resource — every recorded decision about one order, oldest first.
--
-- 7.3 hands the learner two blocked attempts on the same resource and asks which one a control
-- stopped. The answer is visible here, and so is the absence that makes it visible: a request
-- rejected by schema validation never reached the pipeline, so it has no row at all.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.decisions_for_resource(p_resource text)
RETURNS TABLE (
  at text, actor text, action text, decision text, reason text, policy_version text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT to_char(e.occurred_at, 'HH24:MI:SS'),
         e.actor_type,
         e.action,
         e.decision,
         e.reason,
         coalesce(e.policy_version, '(none)')
  FROM app.audit_events e
  WHERE e.resource_id = p_resource AND e.actor_type <> 'range'
  ORDER BY e.occurred_at DESC
  LIMIT 30;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.recent_decisions()',
    'range.decisions_for_resource(text)'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0016_range_audit_observations');

RESET ROLE;
COMMIT;
