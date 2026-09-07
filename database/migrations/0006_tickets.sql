-- 0006 — Tickets and ticket messages.
--
-- ticket_messages is the table that carries untrusted external content: customer replies, and in
-- the local environment the stored prompt-injection corpus. Nothing downstream may treat a message
-- body as an instruction.
--
-- It also has a second filter beyond tenancy. A message marked 'restricted' is excluded for
-- support_agent at the database layer, so an application bug cannot expose it.

BEGIN;

SET ROLE sp_migrator_role;

-- ------------------------------------------------------------------------------------------------
-- Role context.
--
-- The API sets app.roles alongside app.user_id and app.organization_id, from the memberships it
-- loaded for the tenant being accessed — never from the token and never from a tool argument.
--
-- Returns an empty array when unset, so a policy that tests for a role fails closed. Note what this
-- is and is not: it lets the *database* apply a visibility rule that the API also applies. It is a
-- second layer, not the authorization decision, which stays with OPA.
-- ------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.current_roles() RETURNS text[]
LANGUAGE sql STABLE
AS $$
  SELECT coalesce(
    string_to_array(nullif(current_setting('app.roles', true), ''), ','),
    ARRAY[]::text[]
  )
$$;

ALTER FUNCTION app.current_roles() OWNER TO sp_migrator_role;
REVOKE EXECUTE ON FUNCTION app.current_roles() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION app.current_roles() TO sp_api_role, sp_worker_role, sp_auditor_role;

CREATE TABLE app.tickets (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  customer_id      uuid NOT NULL REFERENCES app.customers(id),
  ticket_number    text NOT NULL,
  subject          text NOT NULL,
  assigned_team    text,
  status           text NOT NULL CHECK (status IN ('open', 'pending', 'resolved', 'closed')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, ticket_number)
);

CREATE TABLE app.ticket_messages (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  ticket_id        uuid NOT NULL REFERENCES app.tickets(id),
  author_kind      text NOT NULL CHECK (author_kind IN ('customer', 'agent', 'system')),
  body             text NOT NULL,
  visibility       text NOT NULL DEFAULT 'public'
                   CHECK (visibility IN ('public', 'internal', 'restricted')),
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tickets_org_number   ON app.tickets (organization_id, ticket_number);
CREATE INDEX tickets_org_customer ON app.tickets (organization_id, customer_id);
CREATE INDEX ticket_messages_thread
  ON app.ticket_messages (organization_id, ticket_id, created_at);

ALTER TABLE app.tickets         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.tickets         FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ticket_messages FORCE  ROW LEVEL SECURITY;

CREATE POLICY tickets_tenant_read ON app.tickets FOR SELECT TO sp_api_role
USING (organization_id = app.current_org());

-- Tenancy, and then visibility. app.current_roles() is set from the caller's verified memberships
-- for the tenant being accessed; a restricted message is invisible unless the caller holds a role
-- that may see it. Missing role context means restricted messages stay hidden.
CREATE POLICY ticket_messages_tenant_read ON app.ticket_messages FOR SELECT TO sp_api_role
USING (
  organization_id = app.current_org()
  AND (
    visibility <> 'restricted'
    OR app.current_roles() && ARRAY['support_manager', 'auditor']
  )
);

GRANT SELECT (id, organization_id, customer_id, ticket_number, subject,
              assigned_team, status, created_at, updated_at)
  ON app.tickets TO sp_api_role;

GRANT SELECT (id, organization_id, ticket_id, author_kind, body, visibility, created_at)
  ON app.ticket_messages TO sp_api_role;

INSERT INTO app.schema_migrations (version) VALUES ('0006_tickets');

RESET ROLE;
COMMIT;
