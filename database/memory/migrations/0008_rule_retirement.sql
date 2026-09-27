-- 0008 — Retiring a rule, and the whole life of a rule enforced in one place.
--
-- 0004 gave a rule two ways in (proposed, or born active under 9.7's setting) and one decision. It
-- gave it no way out. An active rule is obeyed on every turn for everyone in the organisation, so a
-- rule that cannot be withdrawn is worse than one that was never approved: the mistake is permanent.
-- This file adds the way out, twice:
--
--   * an approver may retire an active rule, through a runtime route the model does not have;
--   * the Range may retire the rules that became active *without* an approval — the debris 9.7
--     leaves behind. Restoring `rules.self_activate` stops new rules activating themselves; it does
--     nothing to the ones that already did, exactly as restoring `forget.scope` does nothing to the
--     copies 9.8 left. Recovery is a separate act from closing the hole.
--
-- A second UPDATE policy creates a trap worth naming. PostgreSQL combines permissive policies with
-- OR, separately for USING and for WITH CHECK, so with `rules_decide` and `rules_retire` both in
-- place an approver could pick the USING clause of one and the WITH CHECK clause of the other: take
-- an active rule (retire's USING) and write it back as active with themselves as `decided_by`
-- (decide's WITH CHECK) — forging who approved it. Policies describe which rows; they cannot
-- describe transitions. So the transitions move into the trigger, as a complete table, and the
-- policies only say who may touch which rows.

SET ROLE mem_migrator;

ALTER TABLE mem.rules ADD COLUMN retired_by text;
ALTER TABLE mem.rules ADD COLUMN retired_at timestamptz;

-- ------------------------------------------------------------------------------------------------
-- Every legal change to a rule, and nothing else:
--
--   proposed -> active | rejected   decided by somebody other than the proposer
--   active   -> retired             who approved it stays exactly as it was
--   rejected, retired               final
--
-- The text, its hash and its proposer never change — the column grants already refuse the service,
-- and this refuses everyone else, including the owner the Range's function runs as.
-- ------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION mem.enforce_rule_separation() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.text IS DISTINCT FROM OLD.text
     OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash
     OR NEW.proposed_by IS DISTINCT FROM OLD.proposed_by
     OR NEW.proposed_channel IS DISTINCT FROM OLD.proposed_channel
     OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
    RAISE EXCEPTION 'a rule''s text, proposer and organisation never change'
      USING ERRCODE = 'raise_exception';
  END IF;

  IF OLD.state = 'proposed' THEN
    IF NEW.state NOT IN ('active', 'rejected') THEN
      RAISE EXCEPTION 'a proposal can only be approved or rejected'
        USING ERRCODE = 'raise_exception';
    END IF;
    IF NEW.decided_by IS NULL THEN
      RAISE EXCEPTION 'a rule decision must name who decided it'
        USING ERRCODE = 'raise_exception';
    END IF;
    IF NEW.decided_by = OLD.proposed_by THEN
      RAISE EXCEPTION 'separation of duty: the proposer may not decide their own rule'
        USING ERRCODE = 'raise_exception';
    END IF;
    IF NEW.retired_by IS NOT NULL THEN
      RAISE EXCEPTION 'a proposal cannot be retired' USING ERRCODE = 'raise_exception';
    END IF;

  ELSIF OLD.state = 'active' THEN
    IF NEW.state <> 'retired' THEN
      RAISE EXCEPTION 'an active rule can only be retired' USING ERRCODE = 'raise_exception';
    END IF;
    IF NEW.decided_by IS DISTINCT FROM OLD.decided_by
       OR NEW.decided_at IS DISTINCT FROM OLD.decided_at THEN
      RAISE EXCEPTION 'retiring a rule does not change who approved it'
        USING ERRCODE = 'raise_exception';
    END IF;
    IF NEW.retired_by IS NULL THEN
      RAISE EXCEPTION 'a retirement must name who retired it' USING ERRCODE = 'raise_exception';
    END IF;

  ELSE
    RAISE EXCEPTION 'a % rule is final', OLD.state USING ERRCODE = 'raise_exception';
  END IF;
  RETURN NEW;
END
$$;

-- Retire: an approver, in the organisation, on an active rule.
CREATE POLICY rules_retire ON mem.rules FOR UPDATE TO mem_service_role
USING (
  org_id = mem.org_id()
  AND state = 'active'
  AND (mem.has_role('support_manager') OR mem.has_role('finance_approver'))
)
WITH CHECK (org_id = mem.org_id() AND state = 'retired');

GRANT UPDATE (retired_by, retired_at) ON mem.rules TO mem_service_role;

-- ------------------------------------------------------------------------------------------------
-- The Range's recovery for 9.7: retire every rule that is active although nobody approved it.
--
-- Only those. A rule someone approved is somebody's decision, and the Range does not get to undo
-- it. The owner's policy is written to that shape, so even this function cannot reach an approved
-- rule — the WHERE clause is not the only thing saying so.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY rules_owner_retire_unapproved ON mem.rules FOR UPDATE TO mem_migrator
USING (state = 'active' AND decided_by IS NULL)
WITH CHECK (state = 'retired' AND decided_by IS NULL);

CREATE FUNCTION range_mem.retire_unapproved_rules() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
DECLARE
  retired integer := 0;
  r record;
BEGIN
  FOR r IN
    UPDATE mem.rules SET state = 'retired', retired_by = 'the-range', retired_at = now()
    WHERE state = 'active' AND decided_by IS NULL
    RETURNING id, org_id
  LOOP
    retired := retired + 1;
    -- Evidence in the same transaction, one event per rule. If any insert fails, none retired.
    INSERT INTO mem.audit_events (request_id, actor_type, actor_sub, org_id, action, resource_type,
                                  resource_id, decision, reason)
    VALUES ('range-' || gen_random_uuid(), 'range', 'the-range', r.org_id, 'rule.retire', 'rule',
            r.id::text, 'succeeded', 'retired:activated_without_approval');
  END LOOP;
  RETURN retired;
END
$$;

REVOKE ALL ON FUNCTION range_mem.retire_unapproved_rules() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range_mem.retire_unapproved_rules() TO mem_range_role;

RESET ROLE;
