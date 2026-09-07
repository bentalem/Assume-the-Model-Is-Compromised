-- 0009 — Correct the API's write policies on action tables.
--
-- 0008 was wrong in two ways, both found by running the approval flow end to end:
--
--   1. action_requests_api_update allowed the API to touch only PROPOSED rows. The reasoning was
--      "the API only moves a request to PENDING_APPROVAL; later transitions belong to the approval
--      portal". But the portal has no database credential *by design* — it reaches the database
--      only through the API. So the API legitimately performs the approval transition too, acting
--      for an authenticated approver. With the old policy every approval failed.
--
--   2. There was no INSERT policy on action_jobs for the API, so enqueuing an approved action was
--      refused. The grant existed; the row policy did not.
--
-- The fix keeps the boundary that actually matters. The API may move a request to
-- PENDING_APPROVAL, APPROVED, or REJECTED — and no further. QUEUED, EXECUTING, SUCCEEDED and
-- FAILED remain writable only by the worker, so the request path still cannot drive an action to
-- execution.

BEGIN;

SET ROLE sp_migrator_role;

DROP POLICY action_requests_api_update ON app.action_requests;

CREATE POLICY action_requests_api_update ON app.action_requests FOR UPDATE TO sp_api_role
USING (
  organization_id = app.current_org()
  AND (
    -- The requester moving their own proposal forward for review.
    (state = 'PROPOSED' AND requester_id = app.current_user_id())
    -- An approver recording a decision. The role comes from server-side memberships, and the
    -- separation-of-duty trigger on approval_decisions still refuses a self-approval.
    OR (state = 'PENDING_APPROVAL' AND app.current_roles() && ARRAY['finance_approver'])
  )
)
WITH CHECK (
  organization_id = app.current_org()
  -- The ceiling. An approved action is handed to the worker; the API cannot queue or execute it.
  AND state IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED')
);

-- The API enqueues a job when, and only when, it records an approval. The EXISTS clause is what
-- ties the two together: a queue entry cannot be created for an action that was not approved.
CREATE POLICY action_jobs_api_insert ON app.action_jobs FOR INSERT TO sp_api_role
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM app.action_requests r
    JOIN app.approval_decisions d ON d.action_request_id = r.id
    WHERE r.id = action_request_id
      AND r.organization_id = app.current_org()
      AND r.state = 'APPROVED'
      AND d.decision = 'approved'
  )
);

INSERT INTO app.schema_migrations (version) VALUES ('0009_fix_action_transitions');

RESET ROLE;
COMMIT;
