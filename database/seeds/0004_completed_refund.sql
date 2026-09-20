-- One completed refund, as fixture history.
--
-- Challenge 7.1 asks a learner to reconstruct a finished sensitive action from the audit trail. On
-- a fresh lab the trail is empty, so without this file the challenge works only for someone who has
-- already run the verification suite or walked through Part A — which is a challenge that fails for
-- the next person. docs/architecture/the-range.md predicted exactly that and called for a seeded
-- evidence path; this is it.
--
-- This is fiction, in the same sense that the customers and orders in 0001 are fiction, and it is
-- consistent fiction: the action request, its approval, its job, its execution evidence and its four
-- audit rows all exist and all agree. A learner who follows result_reference out of the trail and
-- into app.action_requests finds the row it names. A trail whose references led nowhere would teach
-- the wrong lesson in a challenge about whether evidence holds up.
--
-- Two details are real rather than decorative:
--
--   * The payload hash is the actual sha256 of the canonical payload below, computed the way
--     services/api/src/supportpilot_api/actions/state.py computes it — sorted keys, no insignificant
--     whitespace. The same hash appears on the request, on the approval and on three audit rows,
--     because that agreement is the thing 7.1 asks the learner to verify. A made-up hash would make
--     the exercise's answer false.
--   * alice proposes and fiona approves. Not because the separation of duty trigger is bypassed
--     here, but because it is not: approval_decisions carries a BEFORE INSERT trigger that refuses a
--     self-approval, and a fixture that tried to seed one would fail this file rather than quietly
--     produce a trail that the system could never have written.
--
-- Timestamps are fixed and in the past, so the reconstruction reads the same for everyone.
--
-- Every insert is ON CONFLICT DO NOTHING against a fixed id. The migrate job runs every seed on
-- every `compose up`, so a seed that is not idempotent fails the whole job the second time somebody
-- starts the lab — which is exactly how this one was found.

BEGIN;

INSERT INTO app.action_requests
  (id, organization_id, requester_id, action_type, resource_type, resource_id,
   payload, payload_hash, state, risk_level, expires_at, created_at, updated_at)
VALUES (
  'fa110001-0000-0000-0000-000000000001',
  '11111111-1111-1111-1111-111111111111',
  'a1111111-1111-1111-1111-111111111111',
  'refund', 'order', 'ORD-2001',
  '{"action_type":"refund","amount":"72.50","currency":"USD","order_number":"ORD-2001","organization_id":"11111111-1111-1111-1111-111111111111","reason":"service_not_delivered"}'::jsonb,
  '6b87102707746120f567e1a21d7cf6342624db5e0f0b8c02c2aa64a0eb808317',
  'SUCCEEDED', 'high',
  TIMESTAMPTZ '2026-09-01 09:20:00+00',
  TIMESTAMPTZ '2026-09-01 09:05:00+00',
  TIMESTAMPTZ '2026-09-01 09:06:14+00'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.approval_decisions
  (id, action_request_id, approver_id, decision, approved_hash, comment, policy_version, decided_at)
VALUES (
  'fa110004-0000-0000-0000-000000000001',
  'fa110001-0000-0000-0000-000000000001',
  'f1111111-1111-1111-1111-111111111111',
  'approved',
  '6b87102707746120f567e1a21d7cf6342624db5e0f0b8c02c2aa64a0eb808317',
  'Delivery confirmed undelivered by the carrier. Amount matches the order line.',
  '2026-09-07.1',
  TIMESTAMPTZ '2026-09-01 09:06:02+00'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.action_jobs
  (id, action_request_id, state, attempts, max_attempts, available_at, created_at)
VALUES (
  'fa110002-0000-0000-0000-000000000001',
  'fa110001-0000-0000-0000-000000000001',
  'SUCCEEDED', 1, 3,
  TIMESTAMPTZ '2026-09-01 09:06:02+00',
  TIMESTAMPTZ '2026-09-01 09:06:02+00'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.action_executions
  (id, job_id, idempotency_key, provider, provider_reference, outcome, detail, started_at, finished_at)
VALUES (
  'fa110003-0000-0000-0000-000000000001',
  'fa110002-0000-0000-0000-000000000001',
  'fa110001-0000-0000-0000-000000000001:6b87102707746120f567e1a21d7cf634',
  'fake', 're_5f2c9a41b7de08c3a614', 'succeeded', NULL,
  TIMESTAMPTZ '2026-09-01 09:06:12+00',
  TIMESTAMPTZ '2026-09-01 09:06:14+00'
)
ON CONFLICT (id) DO NOTHING;

-- The trail. Four rows, four request ids, three actors — which is the whole point of 7.1.
INSERT INTO app.audit_events
  (event_id, occurred_at, request_id, actor_type, actor_id, organization_id,
   action, resource_type, resource_id, decision, reason, policy_version,
   payload_hash, result_reference)
VALUES
  ('fa11e001-0000-0000-0000-000000000001', TIMESTAMPTZ '2026-09-01 09:05:58+00',
   'req-7c1d4a90-0e55-4f2b-9a31-5d8e0c47b112', 'user',
   'a1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111',
   'refund.propose', 'order', 'ORD-2001', 'succeeded', 'action_pending_approval', '2026-09-07.1',
   '6b87102707746120f567e1a21d7cf6342624db5e0f0b8c02c2aa64a0eb808317',
   'fa110001-0000-0000-0000-000000000001'),

  ('fa11e002-0000-0000-0000-000000000001', TIMESTAMPTZ '2026-09-01 09:05:59+00',
   'req-2b93f10c-6a47-41d8-8e02-71c4ab35d6f9', 'user',
   'f1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111',
   'refund.approve.view', 'action_request', 'fa110001-0000-0000-0000-000000000001',
   'allowed', 'independent_approver_verified', '2026-09-07.1', NULL, NULL),

  ('fa11e003-0000-0000-0000-000000000001', TIMESTAMPTZ '2026-09-01 09:06:02+00',
   'req-9d50e8b7-3c11-4a6e-b28f-0af7c96d1e34', 'user',
   'f1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111',
   'refund.approve', 'action_request', 'fa110001-0000-0000-0000-000000000001',
   'approved', 'independent_approval_recorded', '2026-09-07.1',
   '6b87102707746120f567e1a21d7cf6342624db5e0f0b8c02c2aa64a0eb808317', NULL),

  ('fa11e004-0000-0000-0000-000000000001', TIMESTAMPTZ '2026-09-01 09:06:14+00',
   'worker-4e8a1c23-95b6-4d70-a1f3-8c2b5e097da6', 'workload',
   'worker-1', '11111111-1111-1111-1111-111111111111',
   'refund.execute', 'action_request', 'fa110001-0000-0000-0000-000000000001',
   'succeeded', 'succeeded', NULL,
   '6b87102707746120f567e1a21d7cf6342624db5e0f0b8c02c2aa64a0eb808317',
   're_5f2c9a41b7de08c3a614')
ON CONFLICT (event_id) DO NOTHING;

COMMIT;
