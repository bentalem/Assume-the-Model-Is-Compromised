-- 0018 — The Range: challenge 6.1, payload binding.
--
-- The attack is the oldest one against any approval workflow: get a small thing approved, then
-- change it before it executes. The control is that the approval binds to a *hash of the payload*,
-- and the worker recomputes that hash immediately before calling the provider.
--
-- The mutation here changes the amount in a pending request's payload and leaves payload_hash
-- alone — which is precisely the attack, because an attacker who could also update the hash would
-- not need the attack.
--
-- What this file deliberately does NOT do is recompute the hash in SQL.
--
-- It would be easy to add `digest(payload::text, 'sha256')` and show a mismatch. It would also be
-- wrong: the worker canonicalises the payload in Python before hashing, and a SQL reimplementation
-- that disagreed about key order or separators would produce a mismatch for the wrong reason. The
-- observation would then be demonstrating a bug in itself while claiming to demonstrate a control —
-- which is the failure mode track 7 spends a whole challenge on.
--
-- So the observation shows what it can honestly show: the payload, the hash the approval is bound
-- to, and whether the payload has been altered since. The recomputation stays where it belongs, in
-- the worker, and Stage 03 shows that code.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.arm_tamper_payload() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  UPDATE app.action_requests
  SET payload = jsonb_set(payload, '{amount}', '"4500.00"')
  WHERE id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

CREATE FUNCTION range.restore_payload() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  UPDATE app.action_requests
  SET payload = jsonb_set(payload, '{amount}', '"45.00"')
  WHERE id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

-- ------------------------------------------------------------------------------------------------
-- range.payload_binding — what the approval is bound to, and what is in the payload now.
--
-- `altered` is decided by comparing the amount against the value this lab seeds, not by a hash
-- computation, so the column says exactly what it can support and nothing more.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range.payload_binding()
RETURNS TABLE (
  action_id text, state text, amount text, currency text,
  payload_hash text, approved_hash text, altered text
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
              THEN 'no — payload is as proposed'
              ELSE 'YES — payload changed, hash did not'
         END
  FROM app.action_requests r
  LEFT JOIN app.approval_decisions d ON d.action_request_id = r.id
  WHERE r.state = 'PENDING_APPROVAL'
  ORDER BY r.created_at DESC
  LIMIT 5;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_tamper_payload()',
    'range.restore_payload()',
    'range.payload_binding()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

-- The tamper mutation updates action_requests, so the migration role needs an UPDATE policy. Scoped
-- to the payload column's table and to pending requests only: nothing here should be able to touch a
-- request that has already executed, because rewriting the record of something that happened is a
-- different and much worse thing than changing something that has not.
CREATE POLICY actions_migrator_update ON app.action_requests FOR UPDATE TO sp_migrator_role
USING (state = 'PENDING_APPROVAL')
WITH CHECK (state = 'PENDING_APPROVAL');

INSERT INTO app.schema_migrations (version) VALUES ('0018_range_payload_binding');

RESET ROLE;
COMMIT;
