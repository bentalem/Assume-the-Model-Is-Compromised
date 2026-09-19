-- 0019 — `payload_binding` was reporting tampering it could not detect.
--
-- The `altered` column compared the amount against '45.00' and said "YES — payload changed, hash
-- did not" for anything else. An older pending request in this lab was proposed at 1.00 and had
-- never been touched, and the observation accused it anyway.
--
-- That is a false positive in an investigative tool, which is worse than a missing column: a
-- learner shown a tampering indicator that fires on untampered rows learns to ignore the indicator,
-- and a reviewer who reports it has made exactly the mistake track 7 is about.
--
-- Two changes, and the second is the real one:
--
--   1. The observation now shows only the request the mutation acts on — the newest pending one —
--      so the comparison is about a row this function actually knows something about.
--
--   2. The column is renamed to say what it checks. It does not detect tampering; it reports
--      whether the amount differs from the value this challenge proposes. Those are different
--      claims, and only the second one is true.
--
-- The detection of tampering lives where it belongs: in the worker, which recomputes the hash and
-- refuses. Stage 03 shows that code, and the point of the challenge is that this observation
-- *cannot* do the worker's job.

BEGIN;

SET ROLE sp_migrator_role;

DROP FUNCTION range.payload_binding();

CREATE FUNCTION range.payload_binding()
RETURNS TABLE (
  action_id text, state text, amount text, currency text,
  payload_hash text, approved_hash text, matches_proposal text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT left(r.id::text, 8) || '…',
         r.state,
         r.payload ->> 'amount',
         r.payload ->> 'currency',
         left(r.payload_hash, 16) || '…',
         coalesce(left(d.approved_hash, 16) || '…', '(not approved yet)'),
         CASE WHEN r.payload ->> 'amount' = '45.00'
              THEN 'yes — 45.00, as proposed'
              ELSE 'no — the amount is not the proposed 45.00'
         END
  FROM app.action_requests r
  LEFT JOIN app.approval_decisions d ON d.action_request_id = r.id
  WHERE r.id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

ALTER FUNCTION range.payload_binding() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.payload_binding() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.payload_binding() TO sp_range_role;

INSERT INTO app.schema_migrations (version) VALUES ('0019_range_payload_binding_honest');

RESET ROLE;
COMMIT;
