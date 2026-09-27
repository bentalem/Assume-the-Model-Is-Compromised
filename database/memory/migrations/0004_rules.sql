-- 0004 — Procedural memory: rules the agent follows.
--
-- A rule is not data the agent reads. It is an instruction it obeys, on every turn, for every user
-- it applies to. That makes changing one a control-plane change, and when it goes wrong it is made
-- from inside the request path — the agent proposing a rule for itself after reading something.
--
-- So a rule is proposed, and becomes active only when somebody other than the proposer approves
-- it: the same propose → approve → execute structure track 6 teaches for refunds, applied to a new
-- kind of state. The separation is enforced here, by a trigger, so it holds even if both the
-- service and whoever called it are wrong.
--
-- Challenge 9.7 arms `rules.self_activate`, which lets a proposal be born active — the
-- configuration of every assistant that "learns your preferences" by writing them straight into
-- the rules it follows.

SET ROLE mem_migrator;

CREATE TABLE mem.rules (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL,
  text             text NOT NULL CHECK (length(text) BETWEEN 1 AND 500),
  version          integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  state            text NOT NULL CHECK (state IN ('proposed', 'active', 'rejected', 'retired')),
  proposed_by      text NOT NULL,
  proposed_channel text NOT NULL CHECK (proposed_channel IN ('agent', 'user', 'seed')),
  -- sha256 of the text. An approval binds to this, not to the row id, so what was approved is
  -- provably what became active.
  payload_hash     text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  decided_by       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  decided_at       timestamptz
);

CREATE INDEX rules_org_state ON mem.rules (org_id, state);

-- ------------------------------------------------------------------------------------------------
-- Separation of duty, in the database.
--
-- A trigger rather than a CHECK because the rule relates two moments of one row — who proposed it
-- and who is now deciding — and it has to hold no matter which code path performs the update.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION mem.enforce_rule_separation() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.state = 'proposed' AND NEW.state IN ('active', 'rejected') THEN
    IF NEW.decided_by IS NULL THEN
      RAISE EXCEPTION 'a rule decision must name who decided it';
    END IF;
    IF NEW.decided_by = OLD.proposed_by THEN
      RAISE EXCEPTION 'separation of duty: the proposer may not decide their own rule'
        USING ERRCODE = 'raise_exception';
    END IF;
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER rules_separation_of_duty
BEFORE UPDATE ON mem.rules
FOR EACH ROW EXECUTE FUNCTION mem.enforce_rule_separation();

ALTER TABLE mem.rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.rules FORCE  ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------------------------
-- Read: active rules in your organisation, which is what context assembly needs; your own
-- proposals; and every proposal if you are one of the people who approve them.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY rules_read ON mem.rules FOR SELECT TO mem_service_role
USING (
  org_id = mem.org_id()
  AND (
    state = 'active'
    OR proposed_by = mem.user_sub()
    OR mem.has_role('support_manager')
    OR mem.has_role('finance_approver')
  )
);

-- Propose: in your organisation, as yourself, as a proposal. Born active only if the setting says
-- a rule may activate itself.
CREATE POLICY rules_insert ON mem.rules FOR INSERT TO mem_service_role
WITH CHECK (
  org_id = mem.org_id()
  AND proposed_by = mem.user_sub()
  AND (
    state = 'proposed'
    OR (state = 'active' AND mem.setting('rules.self_activate') = 'true')
  )
);

-- Decide: an approver, in the organisation, on a proposal. The trigger above adds that it must be
-- a different person; the column grant below means the text itself can never be changed.
CREATE POLICY rules_decide ON mem.rules FOR UPDATE TO mem_service_role
USING (
  org_id = mem.org_id()
  AND state = 'proposed'
  AND (mem.has_role('support_manager') OR mem.has_role('finance_approver'))
)
WITH CHECK (org_id = mem.org_id() AND state IN ('active', 'rejected'));

CREATE POLICY rules_owner_read ON mem.rules FOR SELECT TO mem_migrator USING (true);

GRANT SELECT, INSERT ON mem.rules TO mem_service_role;
GRANT UPDATE (state, decided_by, decided_at) ON mem.rules TO mem_service_role;

REVOKE ALL ON FUNCTION mem.enforce_rule_separation() FROM PUBLIC;

RESET ROLE;
