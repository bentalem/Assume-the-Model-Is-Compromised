-- 0027 — The Range: reconstructing one action from the trail, for challenge 7.1.
--
-- 7.1 hands the learner a finished refund and asks the six questions an investigator asks: who
-- asked, who approved, for what, under which rules, what was decided, what changed. The point of
-- the exercise is that no single audit row answers them. A refund spans four requests made by three
-- different actors, and the thing that links them is a column, not a session.
--
-- Two functions. The first assembles the chain. The second reports which audit columns are actually
-- populated, because Stage 03 makes a claim about three columns that nothing ever writes, and a
-- claim like that belongs in a query rather than in prose that was true on the day it was typed.
--
-- Neither function resolves actor_id to a person, and that is deliberate rather than an omission.
-- The trail stores an identifier; naming it is the directory's job. Resolving it here would mean
-- granting the Range read access to app.users so that a teaching page could save the learner one
-- lookup, and the lookup is part of what an investigator does. The baseline in LAB.md maps the
-- identifiers.

BEGIN;

SET ROLE sp_migrator_role;

-- ------------------------------------------------------------------------------------------------
-- range.reconstruct_last_refund — every recorded step of the most recently executed refund.
--
-- The chain is found by the link the system actually uses: the proposal records the new action's id
-- in result_reference, and every later step carries that id as its resource_id. There is no shared
-- request id, no session id and no trace id to group them by — see range.audit_column_use().
--
-- Ordered oldest first, because reconstruction reads forwards.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.reconstruct_last_refund()
RETURNS TABLE (
  at text, request_id text, actor_type text, actor text, action text,
  resource text, decision text, reason text, policy_version text,
  payload_hash text, result_reference text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  WITH last_executed AS (
    SELECT e.resource_id AS action_id
    FROM app.audit_events e
    WHERE e.action = 'refund.execute' AND e.decision = 'succeeded' AND e.resource_id IS NOT NULL
    ORDER BY e.occurred_at DESC
    LIMIT 1
  )
  SELECT to_char(e.occurred_at, 'HH24:MI:SS')::text,
         e.request_id::text,
         e.actor_type::text,
         e.actor_id::text,
         e.action::text,
         coalesce(e.resource_id, '-')::text,
         e.decision::text,
         e.reason::text,
         coalesce(e.policy_version, '(none)')::text,
         coalesce(left(e.payload_hash, 16), '-')::text,
         coalesce(e.result_reference, '-')::text
  FROM app.audit_events e, last_executed l
  WHERE e.resource_id = l.action_id OR e.result_reference = l.action_id
  ORDER BY e.occurred_at
  LIMIT 20;
$$;

-- ------------------------------------------------------------------------------------------------
-- range.audit_column_use — how many rows actually carry each column.
--
-- app.audit_events declares trace_id, previous_event_hash and event_hash. The API's INSERT does not
-- name the two hash columns at all, and nothing supplies trace_id, so all three are empty in every
-- row ever written. That is worth showing rather than telling: a schema is a statement of intent,
-- and the question "is this control present" is answered by counting, not by reading the DDL.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.audit_column_use()
RETURNS TABLE (column_name text, populated bigint, total bigint, verdict text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  WITH counted AS (
    SELECT 'request_id'::text          AS c, count(request_id)          AS n, count(*) AS t FROM app.audit_events
    UNION ALL SELECT 'actor_id',          count(actor_id),          count(*) FROM app.audit_events
    UNION ALL SELECT 'organization_id',   count(organization_id),   count(*) FROM app.audit_events
    UNION ALL SELECT 'policy_version',    count(policy_version),    count(*) FROM app.audit_events
    UNION ALL SELECT 'payload_hash',      count(payload_hash),      count(*) FROM app.audit_events
    UNION ALL SELECT 'result_reference',  count(result_reference),  count(*) FROM app.audit_events
    UNION ALL SELECT 'trace_id',          count(trace_id),          count(*) FROM app.audit_events
    UNION ALL SELECT 'previous_event_hash', count(previous_event_hash), count(*) FROM app.audit_events
    UNION ALL SELECT 'event_hash',        count(event_hash),        count(*) FROM app.audit_events
  )
  SELECT c, n, t,
         CASE
           WHEN n = 0 THEN 'declared, never written'
           WHEN n = t THEN 'always present'
           ELSE 'present where it applies'
         END::text
  FROM counted
  ORDER BY n DESC, c;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.reconstruct_last_refund()',
    'range.audit_column_use()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0027_range_request_reconstruction');

RESET ROLE;
COMMIT;
