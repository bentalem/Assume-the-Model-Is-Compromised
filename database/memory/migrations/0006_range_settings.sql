-- 0006 — The Range's surface in memory-db: read and flip the eight settings, and nothing else.
--
-- The same arrangement as the core's `range` schema. `mem_range_role` owns nothing, holds no table
-- privilege, and may only EXECUTE named functions here. Every one is SECURITY DEFINER, owned by the
-- migration role, so the Range's entire reach into this database is the list of functions in this
-- file and the observation files that follow.
--
-- set_setting is the Range's only write. It accepts a key and a value, and both are checked against
-- fixed lists — a key the code does not know about is refused by the table's CHECK, and a value
-- that is not one of that key's two states is refused here. So the browser that asked for the
-- change could name a setting, and could never invent one.

SET ROLE mem_migrator;

-- The owner may update settings, so that set_setting (which runs as the owner) can. FORCE applies
-- to the owner as well.
CREATE POLICY settings_owner_update ON mem.settings FOR UPDATE TO mem_migrator
USING (true) WITH CHECK (true);

-- ------------------------------------------------------------------------------------------------
-- The two legal values of each setting. The first of each pair is the secure one.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.allowed_values(p_key text) RETURNS text[]
LANGUAGE sql IMMUTABLE
AS $$
  SELECT CASE p_key
    WHEN 'write.secret_filter'  THEN ARRAY['on', 'off']
    WHEN 'context.provenance'   THEN ARRAY['on', 'off']
    WHEN 'history.org_readable' THEN ARRAY['false', 'true']
    WHEN 'history.revalidate'   THEN ARRAY['on', 'off']
    WHEN 'write.auto_confirm'   THEN ARRAY['false', 'true']
    WHEN 'store.layout'         THEN ARRAY['per_tenant', 'shared']
    WHEN 'rules.self_activate'  THEN ARRAY['false', 'true']
    WHEN 'forget.scope'         THEN ARRAY['all', 'primary']
  END
$$;

CREATE FUNCTION range_mem.set_setting(p_key text, p_value text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
DECLARE
  allowed text[] := range_mem.allowed_values(p_key);
  changed integer;
BEGIN
  IF allowed IS NULL THEN
    RAISE EXCEPTION 'unknown setting %', p_key;
  END IF;
  IF NOT p_value = ANY (allowed) THEN
    RAISE EXCEPTION 'setting % cannot be %', p_key, p_value;
  END IF;

  UPDATE mem.settings SET value = p_value, changed_at = now() WHERE key = p_key;
  GET DIAGNOSTICS changed = ROW_COUNT;
  -- A mutation that changes nothing and reports success is the failure this whole registry exists
  -- to prevent. Say so instead.
  IF changed <> 1 THEN
    RAISE EXCEPTION 'setting % not present (% row(s) changed)', p_key, changed;
  END IF;

  -- Evidence in the same transaction as the change. If this insert fails, the setting did not move.
  INSERT INTO mem.audit_events (request_id, actor_type, actor_sub, action, resource_type,
                                resource_id, decision, reason)
  VALUES ('range-' || gen_random_uuid(), 'range', 'the-range', 'range.set_setting', 'setting',
          p_key, 'succeeded',
          CASE WHEN p_value = allowed[1] THEN 'restored:' ELSE 'armed:' END || p_value);

  RETURN p_value;
END
$$;

CREATE FUNCTION range_mem.get_setting(p_key text) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, pg_temp
AS $$ SELECT value FROM mem.settings WHERE key = p_key $$;

-- Whether a setting is at its secure value. What the Range's probes ask.
CREATE FUNCTION range_mem.setting_state(p_key text) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  SELECT CASE
    WHEN s.value IS NULL THEN 'unknown'
    WHEN s.value = (range_mem.allowed_values(p_key))[1] THEN 'correct'
    WHEN s.value = (range_mem.allowed_values(p_key))[2] THEN 'armed'
    ELSE 'unknown'
  END
  FROM (SELECT (SELECT value FROM mem.settings WHERE key = p_key) AS value) s
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range_mem.allowed_values(text)',
    'range_mem.set_setting(text, text)',
    'range_mem.get_setting(text)',
    'range_mem.setting_state(text)'
  ] LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
  END LOOP;
END
$$;

GRANT EXECUTE ON FUNCTION range_mem.set_setting(text, text) TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.get_setting(text)       TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.setting_state(text)     TO mem_range_role;

RESET ROLE;
