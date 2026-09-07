-- 0008 — Action requests, approvals, jobs, executions.
--
-- Three constraints in this file carry the whole duplicate-execution defence, and each is a
-- database rule rather than application logic, so a bug in the API or the worker cannot bypass it:
--
--   one_decision_per_request   a second approval, or an approval replacing a rejection
--   one_job_per_request        two queue entries for one approved action
--   one_effect_per_key         a retry producing a second provider effect
--
-- The worker's grants are deliberately narrow: it can read the frozen payload and move job state,
-- and it has no grant at all on customers, orders, or tickets.

BEGIN;

SET ROLE sp_migrator_role;

-- ------------------------------------------------------------------------------------------------
-- Action requests
-- ------------------------------------------------------------------------------------------------
CREATE TABLE app.action_requests (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  uuid NOT NULL REFERENCES app.organizations(id),
  requester_id     uuid NOT NULL REFERENCES app.users(id),
  action_type      text NOT NULL CHECK (action_type IN ('refund')),
  resource_type    text NOT NULL,
  resource_id      text NOT NULL,
  payload          jsonb NOT NULL,
  -- sha256 of the canonical payload, computed at proposal time and never recomputed from a
  -- mutable source. Approval binds to this value.
  payload_hash     text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  state            text NOT NULL DEFAULT 'PROPOSED'
                   CHECK (state IN ('PROPOSED', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED',
                                    'QUEUED', 'EXECUTING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
  risk_level       text NOT NULL DEFAULT 'high',
  expires_at       timestamptz NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX action_requests_org_state ON app.action_requests (organization_id, state);
CREATE INDEX action_requests_requester ON app.action_requests (requester_id, created_at DESC);

-- ------------------------------------------------------------------------------------------------
-- Approval decisions
-- ------------------------------------------------------------------------------------------------
CREATE TABLE app.approval_decisions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_request_id  uuid NOT NULL REFERENCES app.action_requests(id),
  approver_id        uuid NOT NULL REFERENCES app.users(id),
  decision           text NOT NULL CHECK (decision IN ('approved', 'rejected')),
  -- Must equal action_requests.payload_hash. Stored again here so the approval records *what* was
  -- approved, independently of the request row.
  approved_hash      text NOT NULL CHECK (approved_hash ~ '^[0-9a-f]{64}$'),
  comment            text CHECK (comment IS NULL OR length(comment) <= 2000),
  policy_version     text NOT NULL,
  decided_at         timestamptz NOT NULL DEFAULT now(),

  -- One decision per request, forever. A rejection cannot be replaced by an approval, and an
  -- approval cannot be issued twice.
  CONSTRAINT one_decision_per_request UNIQUE (action_request_id)
);

-- Separation of duty at the database layer. The API and the policy both refuse self-approval; this
-- makes it impossible even if both were wrong. It is a trigger rather than a CHECK because the
-- requester lives in another table and a CHECK cannot reference one.
CREATE FUNCTION app.enforce_separation_of_duty() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  requester uuid;
BEGIN
  SELECT requester_id INTO requester
  FROM app.action_requests
  WHERE id = NEW.action_request_id;

  IF requester IS NULL THEN
    RAISE EXCEPTION 'action request % does not exist', NEW.action_request_id;
  END IF;

  IF requester = NEW.approver_id THEN
    RAISE EXCEPTION 'separation of duty: the requester may not approve their own action'
      USING ERRCODE = 'raise_exception';
  END IF;

  RETURN NEW;
END
$$;

ALTER FUNCTION app.enforce_separation_of_duty() OWNER TO sp_migrator_role;

CREATE TRIGGER approval_separation_of_duty
BEFORE INSERT ON app.approval_decisions
FOR EACH ROW EXECUTE FUNCTION app.enforce_separation_of_duty();

-- ------------------------------------------------------------------------------------------------
-- Worker queue
-- ------------------------------------------------------------------------------------------------
CREATE TABLE app.action_jobs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_request_id  uuid NOT NULL REFERENCES app.action_requests(id),
  state              text NOT NULL DEFAULT 'QUEUED'
                     CHECK (state IN ('QUEUED', 'EXECUTING', 'SUCCEEDED', 'FAILED')),
  attempts           integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts       integer NOT NULL DEFAULT 3,
  lease_owner        text,
  lease_expires_at   timestamptz,
  available_at       timestamptz NOT NULL DEFAULT now(),
  last_error         text,
  created_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT one_job_per_request UNIQUE (action_request_id)
);

CREATE INDEX jobs_claimable ON app.action_jobs (state, available_at)
  WHERE state IN ('QUEUED', 'EXECUTING');

-- ------------------------------------------------------------------------------------------------
-- Execution evidence
-- ------------------------------------------------------------------------------------------------
CREATE TABLE app.action_executions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id              uuid NOT NULL REFERENCES app.action_jobs(id),
  idempotency_key     text NOT NULL,
  provider            text NOT NULL,
  provider_reference  text,
  outcome             text NOT NULL CHECK (outcome IN ('succeeded', 'failed', 'ambiguous')),
  detail              text,
  started_at          timestamptz NOT NULL DEFAULT now(),
  finished_at         timestamptz,

  -- The single most important constraint in the schema: one effect per key, whatever the worker
  -- does. A retry that reaches the provider twice cannot record two successes.
  CONSTRAINT one_effect_per_key UNIQUE (idempotency_key)
);

CREATE INDEX executions_job ON app.action_executions (job_id);

-- ------------------------------------------------------------------------------------------------
-- Row security
-- ------------------------------------------------------------------------------------------------
ALTER TABLE app.action_requests    ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.action_requests    FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.approval_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.approval_decisions FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.action_jobs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.action_jobs        FORCE  ROW LEVEL SECURITY;
ALTER TABLE app.action_executions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.action_executions  FORCE  ROW LEVEL SECURITY;

-- API: tenant-scoped. A requester sees their own actions; approvers and auditors see the tenant's.
CREATE POLICY action_requests_tenant_read ON app.action_requests FOR SELECT TO sp_api_role
USING (
  organization_id = app.current_org()
  AND (
    requester_id = app.current_user_id()
    OR app.current_roles() && ARRAY['support_manager', 'finance_approver', 'auditor']
  )
);

CREATE POLICY action_requests_tenant_insert ON app.action_requests FOR INSERT TO sp_api_role
WITH CHECK (
  organization_id = app.current_org()
  AND requester_id = app.current_user_id()
  AND state = 'PROPOSED'
);

-- The API may move a request only into PENDING_APPROVAL. Every later transition belongs to the
-- approval portal or the worker, so the request path cannot drive an action to execution.
CREATE POLICY action_requests_api_update ON app.action_requests FOR UPDATE TO sp_api_role
USING (organization_id = app.current_org() AND state = 'PROPOSED')
WITH CHECK (organization_id = app.current_org() AND state = 'PENDING_APPROVAL');

CREATE POLICY approval_decisions_tenant_read ON app.approval_decisions FOR SELECT TO sp_api_role
USING (EXISTS (
  SELECT 1 FROM app.action_requests r
  WHERE r.id = app.approval_decisions.action_request_id
    AND r.organization_id = app.current_org()
));

CREATE POLICY approval_decisions_insert ON app.approval_decisions FOR INSERT TO sp_api_role
WITH CHECK (
  approver_id = app.current_user_id()
  AND app.current_roles() && ARRAY['finance_approver']
  AND EXISTS (
    SELECT 1 FROM app.action_requests r
    WHERE r.id = action_request_id
      AND r.organization_id = app.current_org()
      AND r.state = 'PENDING_APPROVAL'
      AND r.expires_at > now()
  )
);

CREATE POLICY action_jobs_tenant_read ON app.action_jobs FOR SELECT TO sp_api_role
USING (EXISTS (
  SELECT 1 FROM app.action_requests r
  WHERE r.id = app.action_jobs.action_request_id
    AND r.organization_id = app.current_org()
));

CREATE POLICY action_executions_tenant_read ON app.action_executions FOR SELECT TO sp_api_role
USING (EXISTS (
  SELECT 1 FROM app.action_jobs j
  JOIN app.action_requests r ON r.id = j.action_request_id
  WHERE j.id = app.action_executions.job_id
    AND r.organization_id = app.current_org()
));

-- Worker: no tenant context at all. It processes the queue across tenants, which is why its grants
-- exclude every business table — the frozen payload is all it gets.
CREATE POLICY action_requests_worker ON app.action_requests FOR SELECT TO sp_worker_role USING (true);
CREATE POLICY action_requests_worker_update ON app.action_requests FOR UPDATE TO sp_worker_role
USING (state IN ('APPROVED', 'QUEUED', 'EXECUTING'))
WITH CHECK (state IN ('QUEUED', 'EXECUTING', 'SUCCEEDED', 'FAILED'));

CREATE POLICY approval_decisions_worker ON app.approval_decisions FOR SELECT TO sp_worker_role USING (true);
CREATE POLICY action_jobs_worker ON app.action_jobs FOR ALL TO sp_worker_role USING (true) WITH CHECK (true);
CREATE POLICY action_executions_worker ON app.action_executions FOR ALL TO sp_worker_role USING (true) WITH CHECK (true);

CREATE POLICY action_requests_auditor ON app.action_requests FOR SELECT TO sp_auditor_role USING (true);
CREATE POLICY approval_decisions_auditor ON app.approval_decisions FOR SELECT TO sp_auditor_role USING (true);
CREATE POLICY action_jobs_auditor ON app.action_jobs FOR SELECT TO sp_auditor_role USING (true);
CREATE POLICY action_executions_auditor ON app.action_executions FOR SELECT TO sp_auditor_role USING (true);

-- ------------------------------------------------------------------------------------------------
-- Grants
-- ------------------------------------------------------------------------------------------------
GRANT SELECT (id, organization_id, requester_id, action_type, resource_type, resource_id,
              payload, payload_hash, state, risk_level, expires_at, created_at, updated_at)
  ON app.action_requests TO sp_api_role;
GRANT INSERT (organization_id, requester_id, action_type, resource_type, resource_id,
              payload, payload_hash, state, risk_level, expires_at)
  ON app.action_requests TO sp_api_role;
GRANT UPDATE (state, updated_at) ON app.action_requests TO sp_api_role;

GRANT SELECT (id, action_request_id, approver_id, decision, approved_hash,
              comment, policy_version, decided_at)
  ON app.approval_decisions TO sp_api_role;
GRANT INSERT (action_request_id, approver_id, decision, approved_hash, comment, policy_version)
  ON app.approval_decisions TO sp_api_role;

GRANT SELECT (id, action_request_id, state, attempts, created_at) ON app.action_jobs TO sp_api_role;
GRANT INSERT (action_request_id) ON app.action_jobs TO sp_api_role;

GRANT SELECT (id, job_id, provider_reference, outcome, started_at, finished_at)
  ON app.action_executions TO sp_api_role;

-- Worker
GRANT SELECT (id, organization_id, requester_id, action_type, resource_type, resource_id,
              payload, payload_hash, state, expires_at)
  ON app.action_requests TO sp_worker_role;
GRANT UPDATE (state, updated_at) ON app.action_requests TO sp_worker_role;
GRANT SELECT ON app.approval_decisions TO sp_worker_role;
GRANT SELECT, UPDATE ON app.action_jobs TO sp_worker_role;
GRANT SELECT, INSERT, UPDATE ON app.action_executions TO sp_worker_role;

-- Auditor
GRANT SELECT ON app.action_requests, app.approval_decisions,
                app.action_jobs, app.action_executions TO sp_auditor_role;

INSERT INTO app.schema_migrations (version) VALUES ('0008_actions');

RESET ROLE;
COMMIT;
