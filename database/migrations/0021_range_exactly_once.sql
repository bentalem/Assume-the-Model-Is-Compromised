-- 0021 — The Range: challenge 6.3, exactly once.
--
-- The lab enforces "once" in three separate places, with three different unique constraints:
--
--   one_decision_per_request   one approval per action request
--   one_job_per_request        one job per action request
--   one_effect_per_key         one execution per idempotency key
--
-- Only the third survives a retry that reaches the provider. The other two stop a duplicate being
-- *created*; this one stops a duplicate being *recorded* no matter how many times the worker tries,
-- which is the case that actually happens — a timeout where nobody knows whether the call landed.
--
-- The observations attempt the duplicate and report which constraint refused, rolling back either
-- way. Same shape as 6.2: the refusal is the subject, so a read could only describe it.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.attempt_duplicate_effect()
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

    DELETE FROM app.action_executions WHERE detail = 'range: 6.3 replay';

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
      SQLERRM::text;
  WHEN others THEN
    RETURN QUERY SELECT
      'replay the same idempotency key'::text, 'refused'::text, 'something else'::text, SQLERRM::text;
  END;
END
$$;

-- The control group. A *different* key is accepted, which is what makes the refusal above a
-- statement about the key rather than about the table.
CREATE FUNCTION range.attempt_new_effect()
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

    DELETE FROM app.action_executions WHERE detail = 'range: 6.3 control';

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

CREATE FUNCTION range.execution_evidence()
RETURNS TABLE (job text, idempotency_key text, provider text, outcome text, reference text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT left(e.job_id::text, 8) || '…',
         left(e.idempotency_key, 20) || '…',
         e.provider,
         e.outcome,
         coalesce(left(e.provider_reference, 18), '(none)')
  FROM app.action_executions e
  ORDER BY e.started_at DESC
  LIMIT 10;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.attempt_duplicate_effect()',
    'range.attempt_new_effect()',
    'range.execution_evidence()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

CREATE POLICY executions_migrator_read   ON app.action_executions FOR SELECT TO sp_migrator_role USING (true);
CREATE POLICY executions_migrator_insert ON app.action_executions FOR INSERT TO sp_migrator_role WITH CHECK (true);
CREATE POLICY executions_migrator_delete ON app.action_executions FOR DELETE TO sp_migrator_role
  USING (detail IN ('range: 6.3 replay', 'range: 6.3 control'));

INSERT INTO app.schema_migrations (version) VALUES ('0021_range_exactly_once');

RESET ROLE;
COMMIT;
