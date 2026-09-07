-- 0004 — Audit events.
--
-- Append-only by grant: no runtime role holds UPDATE or DELETE. The API writes; only the auditor
-- role reads. Evidence is written in the same transaction as the effect it describes, so a failed
-- audit write rolls the effect back (SP-ARCH-001 §10).

BEGIN;

SET ROLE sp_migrator_role;

CREATE TABLE app.audit_events (
  event_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at          timestamptz NOT NULL DEFAULT now(),
  request_id           text NOT NULL,
  trace_id             text,
  actor_type           text NOT NULL CHECK (actor_type IN ('user', 'workload')),
  actor_id             text NOT NULL,
  organization_id      uuid REFERENCES app.organizations(id),
  action               text NOT NULL,
  resource_type        text,
  resource_id          text,
  decision             text NOT NULL CHECK (decision IN ('allowed', 'denied', 'approved',
                                                         'rejected', 'succeeded', 'failed')),
  reason               text NOT NULL,
  policy_version       text,
  payload_hash         text,
  result_reference     text,
  previous_event_hash  text,
  event_hash           text
);

CREATE INDEX audit_request   ON app.audit_events (request_id);
CREATE INDEX audit_org_time  ON app.audit_events (organization_id, occurred_at DESC);
CREATE INDEX audit_action    ON app.audit_events (action, occurred_at DESC);

ALTER TABLE app.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.audit_events FORCE  ROW LEVEL SECURITY;

-- The API may insert an event only for the tenant it is currently acting in, or with no tenant
-- (a denial that happened before tenant context existed, e.g. an unknown resource).
CREATE POLICY audit_insert_own_context ON app.audit_events FOR INSERT TO sp_api_role
WITH CHECK (organization_id IS NOT DISTINCT FROM app.current_org() OR organization_id IS NULL);

CREATE POLICY audit_worker_insert ON app.audit_events FOR INSERT TO sp_worker_role
WITH CHECK (true);

CREATE POLICY audit_auditor_read ON app.audit_events FOR SELECT TO sp_auditor_role
USING (true);

-- Insert only. The API never reads audit events back, and no runtime role can amend one.
GRANT INSERT ON app.audit_events TO sp_api_role, sp_worker_role;
GRANT SELECT ON app.audit_events TO sp_auditor_role;

INSERT INTO app.schema_migrations (version) VALUES ('0004_audit_events');

RESET ROLE;
COMMIT;
