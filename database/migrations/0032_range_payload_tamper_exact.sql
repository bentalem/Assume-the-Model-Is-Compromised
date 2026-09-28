-- 0032 — The payload tamper (6.1) acts on its own request, and restores exactly what it changed.
--
-- 0018 armed and restored "the newest pending refund", and 0019's probe called it armed whenever that
-- refund's amount was not 45.00. Both assumed the newest pending refund was the one challenge 6.1 is
-- about. It is not, as soon as anything else proposes a refund: the contract suite proposes 1.00, the
-- abuse suite 9.90, a learner whatever they like. Then:
--
--   * the probe reported `armed` for a lab nobody had touched, because a genuine 1.00 proposal was
--     the newest pending one;
--   * reset believed it, and "restored" that genuine proposal to 45.00 — rewriting a real request's
--     payload without its hash, which is precisely the tampering 6.1 teaches the worker to refuse.
--
-- A reset that manufactures the defect it exists to remove. The fix has three parts:
--
--   1. The target is the newest pending refund of exactly 45.00 — the one 6.1's content describes —
--      and never anything else. If there is none, arming refuses and says why, rather than choosing
--      a different request.
--   2. Before changing it, the arm records the request and its original payload in
--      range.payload_tamper. Restore puts that payload back byte for byte and forgets the record. It
--      does not write 45.00 into anything; it writes back what was there.
--   3. The probe reads the record, not an amount. Armed means "the Range has changed a payload and
--      not yet put it back" — the one thing it can know for certain.
--
-- A request 0018's arm left at 4500.00 has no record of its own. It is adopted here with the payload
-- 0018's restore would have produced, so the first reset after this migration still repairs it.

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE range.payload_tamper (
  action_request_id  uuid PRIMARY KEY,
  original_payload   jsonb NOT NULL,
  armed_at           timestamptz NOT NULL DEFAULT now()
);
-- No grant: sp_range_role reaches it only through the functions below.
REVOKE ALL ON range.payload_tamper FROM PUBLIC;

INSERT INTO range.payload_tamper (action_request_id, original_payload)
SELECT id, jsonb_set(payload, '{amount}', '"45.00"')
FROM app.action_requests
WHERE state = 'PENDING_APPROVAL' AND payload ->> 'amount' = '4500.00';

CREATE OR REPLACE FUNCTION range.arm_tamper_payload() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  target   uuid;
  original jsonb;
BEGIN
  -- Already armed: one tampered request at a time, and arming twice changes nothing.
  IF EXISTS (SELECT 1 FROM range.payload_tamper) THEN
    RETURN;
  END IF;
  SELECT id, payload INTO target, original
  FROM app.action_requests
  WHERE state = 'PENDING_APPROVAL' AND payload ->> 'amount' = '45.00'
  ORDER BY created_at DESC
  LIMIT 1;
  IF target IS NULL THEN
    RAISE EXCEPTION 'no pending 45.00 refund to alter: propose one first — challenge 6.1 needs a refund of 45.00 awaiting approval';
  END IF;
  INSERT INTO range.payload_tamper (action_request_id, original_payload) VALUES (target, original);
  UPDATE app.action_requests
  SET payload = jsonb_set(payload, '{amount}', '"4500.00"')
  WHERE id = target;
END
$$;

CREATE OR REPLACE FUNCTION range.restore_payload() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
BEGIN
  UPDATE app.action_requests r
  SET payload = t.original_payload
  FROM range.payload_tamper t
  WHERE r.id = t.action_request_id;
  DELETE FROM range.payload_tamper;
END
$$;

CREATE FUNCTION range.payload_tamper_state()
RETURNS TABLE (state text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT CASE WHEN EXISTS (SELECT 1 FROM range.payload_tamper) THEN 'armed' ELSE 'correct' END;
$$;

-- The observation shows the request the mutation acts on: the tampered one while armed, otherwise
-- the one it would act on. "matches_proposal" is now read from the recorded original rather than
-- inferred from an amount, so it cannot accuse a request the Range never touched.
DROP FUNCTION range.payload_binding();

CREATE FUNCTION range.payload_binding()
RETURNS TABLE (
  action_id text, state text, amount text, currency text,
  payload_hash text, approved_hash text, matches_proposal text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  WITH target AS (
    SELECT coalesce(
      (SELECT action_request_id FROM range.payload_tamper LIMIT 1),
      (SELECT id FROM app.action_requests
       WHERE state = 'PENDING_APPROVAL' AND payload ->> 'amount' = '45.00'
       ORDER BY created_at DESC LIMIT 1)
    ) AS id
  )
  SELECT left(r.id::text, 8) || '…',
         r.state,
         r.payload ->> 'amount',
         r.payload ->> 'currency',
         left(r.payload_hash, 16) || '…',
         coalesce(left(d.approved_hash, 16) || '…', '(not approved yet)'),
         CASE WHEN t.action_request_id IS NULL
              THEN 'yes — as proposed'
              ELSE 'no — changed after it was proposed at ' || (t.original_payload ->> 'amount')
         END
  FROM target
  JOIN app.action_requests r ON r.id = target.id
  LEFT JOIN app.approval_decisions d ON d.action_request_id = r.id
  LEFT JOIN range.payload_tamper t ON t.action_request_id = r.id;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_tamper_payload()',
    'range.restore_payload()',
    'range.payload_tamper_state()',
    'range.payload_binding()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0032_range_payload_tamper_exact');

RESET ROLE;
COMMIT;
