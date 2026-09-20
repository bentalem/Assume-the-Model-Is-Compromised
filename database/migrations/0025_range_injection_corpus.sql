-- 0025 — The Range: challenge 5.2, the injection corpus.
--
-- TKT-1001 carries ten instruction-shaped messages written to look like ordinary customer text. The
-- learner needs to read them, so this returns them — bounded, named, and from the database rather
-- than from a probe.
--
-- That split is ADR-0003's own rule and it is worth stating where it applies: a probe reports what a
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
-- Read from the API's own route table would be better still, but the Range has no route to the API
-- and the action document is not in its mount. This reads the tool modules on disk, which is the
-- same source the document is generated from — so a tool added without a module cannot hide here.
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
