-- 0031 — The Range: the delegated side of the audit trail (track 1, 1.5 - 1.8).
--
-- Challenges 1.5 - 1.8 turn on one column. A call made through the broker is recorded with the user
-- as the actor and the agent beside them in `agent_id` (0030); the same call under passthrough is
-- recorded with the user alone, and nothing in the row says an agent made it. The learner has to
-- see those two rows next to each other, so this function shows them — and says "(none)" out loud
-- rather than leaving an empty cell, because the absence is the finding.
--
-- Read only, capped, and named, like every range.* function. The migration role already reads
-- app.audit_events (0016) and app.users (0002), so no new policy or grant on a table is needed.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.delegated_decisions()
RETURNS TABLE (
  at text, person text, agent text, action text, resource text,
  decision text, reason text, policy_version text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT to_char(e.occurred_at, 'HH24:MI:SS'),
         coalesce(u.display_name, e.actor_id),
         coalesce(e.agent_id, '(none: the user alone)'),
         e.action,
         coalesce(e.resource_id, '-'),
         e.decision,
         e.reason,
         coalesce(e.policy_version, '(none)')
  FROM app.audit_events e
  LEFT JOIN app.users u ON u.id::text = e.actor_id
  WHERE e.actor_type = 'user'
    AND e.action IN ('order.read', 'customer.read', 'action.read', 'refund.propose')
  ORDER BY e.occurred_at DESC
  LIMIT 12;
$$;

ALTER FUNCTION range.delegated_decisions() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.delegated_decisions() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.delegated_decisions() TO sp_range_role;

INSERT INTO app.schema_migrations (version) VALUES ('0031_range_delegation');

RESET ROLE;
COMMIT;
