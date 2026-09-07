-- 0007 — Internal notes. The first write path.
--
-- The insert policy is the point of this migration. `author_id = app.current_user_id()` means an
-- author supplied by the model is impossible to honour even if application code were wrong: the
-- database refuses the row. That is the difference between a rule and a check.

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE app.internal_notes (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  ticket_id        uuid NOT NULL REFERENCES app.tickets(id),
  author_id        uuid NOT NULL REFERENCES app.users(id),
  body             text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX internal_notes_thread ON app.internal_notes (organization_id, ticket_id, created_at);

ALTER TABLE app.internal_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.internal_notes FORCE  ROW LEVEL SECURITY;

CREATE POLICY notes_tenant_read ON app.internal_notes FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

-- Three conditions, all from trusted request context rather than the request body:
--   the note belongs to the caller's tenant,
--   the author is the caller,
--   the ticket exists in that same tenant.
CREATE POLICY notes_tenant_insert ON app.internal_notes FOR INSERT TO sp_api_role
WITH CHECK (
  organization_id = app.current_org()
  AND author_id = app.current_user_id()
  AND EXISTS (
    SELECT 1 FROM app.tickets t
    WHERE t.id = app.internal_notes.ticket_id
      AND t.organization_id = app.current_org()
  )
);

-- No UPDATE and no DELETE policy, and no grant for either. A note is an append-only record of what
-- staff said at a point in time; editing it away would defeat its purpose.
GRANT SELECT (id, organization_id, ticket_id, author_id, body, created_at)
  ON app.internal_notes TO sp_api_role;
GRANT INSERT (organization_id, ticket_id, author_id, body)
  ON app.internal_notes TO sp_api_role;

INSERT INTO app.schema_migrations (version) VALUES ('0007_internal_notes');

RESET ROLE;
COMMIT;
