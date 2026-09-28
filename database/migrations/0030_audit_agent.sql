-- 0030 — The agent beside the human, in the audit trail.
--
-- Track 1, challenges 1.5 - 1.8: down-scoped delegation. A delegated token names two parties — the
-- user it acts for (`sub`) and the agent acting (`act`). The audit row keeps attributing the action
-- to the human, exactly as before: `actor_type` stays 'user' and `actor_id` stays the user. What is
-- new is the second column, so an investigator can tell a person from an agent acting for them.
-- Losing `act` in the audit is the failure this column exists to prevent: under passthrough the two
-- are indistinguishable, and challenge 1.5 shows exactly that row.
--
-- The value is the whole delegation chain, in delegation order, joined with ' > ':
--
--     status-helper                         alice delegated to status-helper
--     status-helper > refund-assistant      ... which handed a narrower token to refund-assistant
--
-- The whole chain and not only the agent acting last, because the chain is what challenge 1.8 is
-- about, and a trail that kept one link of it would be failure 7 again by another route.
--
-- Additive. The column is nullable and NULL for every row with no agent, which is every row written
-- before this migration and every row written from a Keycloak token after it. No writer that does
-- not name the column is affected: the API, the worker and the Range each name their columns. The
-- hash-chain columns declared in 0004 are written by nobody (0027 records this), so no chain is
-- disturbed. No grant changes: sp_api_role already holds INSERT on the table, and nothing else.

BEGIN;

SET ROLE sp_migrator_role;

-- Bounded: four hops of 63 characters and their separators fit comfortably, and a value the API
-- never produces is refused by the table rather than trusted.
ALTER TABLE app.audit_events
  ADD COLUMN agent_id text
  CONSTRAINT audit_agent_id_bounded CHECK (agent_id IS NULL OR length(agent_id) BETWEEN 1 AND 300);

INSERT INTO app.schema_migrations (version) VALUES ('0030_audit_agent');

RESET ROLE;
COMMIT;
