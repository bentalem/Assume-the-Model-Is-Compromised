-- 0025 — The Range: challenge 5.2, the injection corpus.
--
-- TKT-1001 carries ten instruction-shaped messages written to look like ordinary customer text. The
-- learner needs to read them, so this returns them — bounded, named, and from the database rather
-- than from a probe.
--
-- That split is the probe service's own rule and it is worth stating where it applies: a probe reports what a
-- *request* did — status, error code, field names — and data comes from an observation, where the
-- row cap and the column list are enforced here rather than in a service that can reach the API.
--
-- The body is truncated. Ten messages of several hundred characters each in a fixed-width result
-- panel is a wall of text nobody reads, and the point of the challenge is to trace each attempt to
-- the thing that made it inert, not to admire the prose.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.injection_corpus()
RETURNS TABLE (n text, author text, visibility text, attempt text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp
AS $$
  SELECT row_number() OVER (ORDER BY m.created_at)::text,
         m.author_kind,
         m.visibility,
         left(regexp_replace(m.body, '\s+', ' ', 'g'), 150)
         || CASE WHEN length(m.body) > 150 THEN '…' ELSE '' END
  FROM app.ticket_messages m
  JOIN app.tickets t ON t.id = m.ticket_id
  WHERE t.ticket_number = 'TKT-1001'
  ORDER BY m.created_at
  LIMIT 20;
$$;

-- What the model can actually call. A learner tracing "use the execute_sql tool" needs to be able
-- to check the claim rather than take this lab's word for it.
--
-- Two corrections to an earlier version of this comment, both of which claimed more than the
-- function does. It does NOT read the tool modules on disk: a SQL function cannot, and the body
-- below is a hand-maintained VALUES list. So the property once claimed here — "a tool added
-- without a module cannot hide" — is exactly backwards: a tool added without an edit to this list
-- would not appear at all. And the action document IS in the Range's mount now; `openapi/` was
-- added for challenge 4.1, so a future version of this observation can read the real published
-- surface instead. `tools.surface` and `tools.descriptions` already do.
--
-- What this list is for, honestly: a short map from operation to module, so a learner can find the
-- code. It is not evidence of what is registered, and no challenge should treat it as such.
CREATE FUNCTION range.registered_tool_modules()
RETURNS TABLE (tool_module text, note text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  SELECT * FROM (VALUES
    ('orders.py',    'get_order'),
    ('customers.py', 'search_customers, get_customer'),
    ('tickets.py',   'get_ticket'),
    ('notes.py',     'add_internal_note'),
    ('actions.py',   'propose_refund, get_action_status')
  ) AS t(tool_module, note);
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range.injection_corpus()',
    'range.registered_tool_modules()'
  ] LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO sp_migrator_role', fn);
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO sp_range_role', fn);
  END LOOP;
END
$$;

CREATE POLICY ticket_messages_migrator_read ON app.ticket_messages FOR SELECT TO sp_migrator_role
USING (true);
CREATE POLICY tickets_migrator_read ON app.tickets FOR SELECT TO sp_migrator_role USING (true);

INSERT INTO app.schema_migrations (version) VALUES ('0025_range_injection_corpus');

RESET ROLE;
COMMIT;
