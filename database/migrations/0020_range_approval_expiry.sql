-- 0020 — The Range: challenge 6.4, approval expiry.
--
-- An approval is a statement about a moment. Without an expiry it is a capability: obtained once,
-- valid forever, and sitting in a table waiting for somebody to find it. The lab gives every action
-- request an `expires_at` and the worker refuses anything past it.
--
-- The mutation moves the window into the past rather than deleting it, because the interesting
-- state is "approved, still pending, and now stale" — which is what a real queue looks like after a
-- provider outage, not a synthetic condition.
--
-- The restore sets a fresh future window rather than remembering the original. That is a deliberate
-- choice: the probe asks "is this request's window in the future", which is the property the system
-- actually cares about, and a restore that recreated an exact timestamp would be restoring a value
-- nothing depends on.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.arm_expire_approval() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  UPDATE app.action_requests
  SET expires_at = now() - interval '2 hours'
  WHERE id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

CREATE FUNCTION range.restore_approval_window() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  UPDATE app.action_requests
  SET expires_at = now() + interval '24 hours'
  WHERE id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

CREATE FUNCTION range.approval_window()
RETURNS TABLE (
  action_id text, state text, expires_at text, server_now text,
  window_status text, minutes text
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT left(r.id::text, 8) || '…',
         r.state,
         to_char(r.expires_at, 'HH24:MI:SS'),
         to_char(now(), 'HH24:MI:SS'),
         CASE WHEN r.expires_at > now() THEN 'open' ELSE 'EXPIRED' END,
         to_char(round(extract(epoch FROM (r.expires_at - now())) / 60), 'FM999999') || ' min'
  FROM app.action_requests r
  WHERE r.id = (
    SELECT id FROM app.action_requests
    WHERE state = 'PENDING_APPROVAL' ORDER BY created_at DESC LIMIT 1
  );
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.arm_expire_approval()',
    'range.restore_approval_window()',
    'range.approval_window()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

INSERT INTO app.schema_migrations (version) VALUES ('0020_range_approval_expiry');

RESET ROLE;
COMMIT;
