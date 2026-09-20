-- 0022 — The cleanup in 0021 could not run.
--
-- Both functions end with `DELETE FROM app.action_executions WHERE detail = '…'`, and both declare
-- an output column called `detail`. PL/pgSQL cannot tell which one is meant and raises
-- "column reference detail is ambiguous".
--
-- The dangerous part is where it did not show up. In `attempt_duplicate_effect` the INSERT raises
-- unique_violation first, so the DELETE is never reached and the function looks perfect. The bug
-- only appears on the path where the insert *succeeds* — which is precisely the path where the
-- cleanup is the thing keeping the promise in the function's own comment: "ACCEPTED — and rolled
-- back by the Range".
--
-- So the version of this code that shipped would have worked in every case except the one where a
-- control had failed, and in that case it would have left a duplicate execution row behind while
-- telling the learner it had removed it. A tool that is correct only when the system is correct is
-- not an instrument.
--
-- Found because the control group — the insert that is *supposed* to succeed — failed for this
-- reason instead of succeeding. Without that control group the challenge would have shipped.

BEGIN;

SET ROLE sp_migrator_role;

CREATE OR REPLACE FUNCTION range.attempt_duplicate_effect()
RETURNS TABLE (attempt text, outcome text, refused_by text, detail text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  existing_key text;
  existing_job uuid;
BEGIN
  SELECT e.idempotency_key, e.job_id INTO existing_key, existing_job
  FROM app.action_executions e
  ORDER BY e.started_at DESC
  LIMIT 1;

  IF existing_key IS NULL THEN
    RETURN QUERY SELECT
      'replay the same idempotency key'::text,
      'nothing has executed yet'::text, '-'::text,
      'approve and execute a refund first'::text;
    RETURN;
  END IF;

  BEGIN
    INSERT INTO app.action_executions (job_id, idempotency_key, provider, outcome, detail)
    VALUES (existing_job, existing_key, 'fake', 'succeeded', 'range: 6.3 replay');

    DELETE FROM app.action_executions e WHERE e.detail = 'range: 6.3 replay';

    RETURN QUERY SELECT
      'replay the same idempotency key'::text,
      'ACCEPTED — and rolled back by the Range'::text,
      'nothing'::text,
      'the same effect was recorded twice; exactly-once is not enforced here'::text;
  EXCEPTION WHEN unique_violation THEN
    RETURN QUERY SELECT
      'replay the same idempotency key'::text,
      'refused'::text,
      'one_effect_per_key'::text,
      'a row with this idempotency key already exists'::text;
  WHEN others THEN
    RETURN QUERY SELECT
      'replay the same idempotency key'::text, 'refused'::text, 'something else'::text, SQLERRM::text;
  END;
END
$$;

CREATE OR REPLACE FUNCTION range.attempt_new_effect()
RETURNS TABLE (attempt text, outcome text, refused_by text, detail text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
DECLARE
  existing_job uuid;
BEGIN
  SELECT e.job_id INTO existing_job FROM app.action_executions e ORDER BY e.started_at DESC LIMIT 1;

  IF existing_job IS NULL THEN
    RETURN QUERY SELECT 'a fresh idempotency key'::text, 'nothing has executed yet'::text,
                        '-'::text, ''::text;
    RETURN;
  END IF;

  BEGIN
    INSERT INTO app.action_executions (job_id, idempotency_key, provider, outcome, detail)
    VALUES (existing_job, 'range-control-' || gen_random_uuid()::text, 'fake', 'succeeded',
            'range: 6.3 control');

    DELETE FROM app.action_executions e WHERE e.detail = 'range: 6.3 control';

    RETURN QUERY SELECT
      'a fresh idempotency key'::text,
      'accepted, then rolled back'::text,
      'nothing'::text,
      'a different key is permitted — so the refusal above is about the key, not the row'::text;
  EXCEPTION WHEN others THEN
    RETURN QUERY SELECT 'a fresh idempotency key'::text, 'refused'::text, 'database'::text,
                        SQLERRM::text;
  END;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0022_range_fix_ambiguous_detail');

RESET ROLE;
COMMIT;
