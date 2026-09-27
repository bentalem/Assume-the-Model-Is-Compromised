-- 0003 — Long-term memory records, and the outbox that keeps the vector store in step.
--
-- `mem.records` is the source of truth for every memory, including its provenance. The vector store
-- (Qdrant) holds a copy of each record for retrieval by meaning, and nothing else: if the two ever
-- disagree, this table is right and Qdrant is the thing to repair.
--
-- Provenance is not decoration. Every record says which channel wrote it — the user, the agent, a
-- tool result, the runtime, or a seed — in which session, and what it was derived from. A memory
-- whose origin nobody recorded cannot be judged later, and "why does the agent believe this?" is
-- the first question in any memory incident.
--
-- The rule that makes track 9 work is in the INSERT policy below, not only in the service: a record
-- written by the agent or taken from a tool result is born `unconfirmed`, and stays out of context
-- until the user confirms it. Challenge 9.5 arms `write.auto_confirm`, which lets such a record be
-- born `confirmed` — the configuration every memory product that "just remembers things" ships.

SET ROLE mem_migrator;

CREATE TABLE mem.records (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL,
  owner_sub     text NOT NULL,
  content       text NOT NULL CHECK (length(content) BETWEEN 1 AND 2000),
  content_hash  text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
  channel       text NOT NULL CHECK (channel IN ('user', 'agent', 'tool_result', 'runtime', 'seed')),
  status        text NOT NULL CHECK (status IN ('unconfirmed', 'confirmed')),
  session_id    uuid REFERENCES mem.sessions(id),
  -- A summary or other derivation points at what it was made from. Forgetting a record has to
  -- find these, or the memory survives inside its own summary — challenge 9.8.
  derived_from  uuid REFERENCES mem.records(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  confirmed_at  timestamptz,
  confirmed_via text CHECK (confirmed_via IS NULL OR confirmed_via IN ('user', 'auto')),
  deleted_at    timestamptz
);

CREATE INDEX records_owner ON mem.records (org_id, owner_sub, created_at DESC);
CREATE INDEX records_derived ON mem.records (derived_from) WHERE derived_from IS NOT NULL;

-- ------------------------------------------------------------------------------------------------
-- The outbox. Qdrant is not transactional, so a record and its vector cannot be written in one
-- step. The record, its audit event and an outbox row commit together here; the service applies
-- the outbox to Qdrant after commit; a reconciliation check proves the two stores agree. If the
-- apply fails, the row stays unapplied and the check names it — which is better than a vector that
-- exists for a record that does not.
-- ------------------------------------------------------------------------------------------------
CREATE TABLE mem.outbox (
  id         bigserial PRIMARY KEY,
  record_id  uuid NOT NULL REFERENCES mem.records(id),
  org_id     uuid NOT NULL,
  op         text NOT NULL CHECK (op IN ('upsert', 'delete')),
  -- Which vector layouts this operation applies to. The service writes both layouts so that arming
  -- 9.6 needs no re-indexing; see docs/architecture/the-range.md for why that is a lab artifact.
  layout     text NOT NULL DEFAULT 'both' CHECK (layout IN ('both', 'per_tenant', 'shared')),
  created_at timestamptz NOT NULL DEFAULT now(),
  applied_at timestamptz
);

CREATE INDEX outbox_pending ON mem.outbox (created_at) WHERE applied_at IS NULL;

ALTER TABLE mem.records ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.records FORCE  ROW LEVEL SECURITY;
ALTER TABLE mem.outbox  ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.outbox  FORCE  ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------------------------
-- Records: your own, in your organisation, not forgotten. Nobody reads anybody else's memories —
-- there is no manager clause here, deliberately. Long-term memory is personal in a way a support
-- transcript is not.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY records_read ON mem.records FOR SELECT TO mem_service_role
USING (org_id = mem.org_id() AND owner_sub = mem.user_sub() AND deleted_at IS NULL);

-- Born unconfirmed if the agent or a tool wrote it — unless the auto-confirm setting is on. The
-- other channels (the user, the runtime, a seed) may be born confirmed, because they are the user's
-- own intent or the system's own bookkeeping, not something the agent decided after reading text.
CREATE POLICY records_insert ON mem.records FOR INSERT TO mem_service_role
WITH CHECK (
  org_id = mem.org_id()
  AND owner_sub = mem.user_sub()
  AND (
    status = 'unconfirmed'
    OR channel IN ('user', 'runtime', 'seed')
    OR mem.setting('write.auto_confirm') = 'true'
  )
);

-- Confirming and forgetting are updates to your own live records, and only to the columns those
-- two operations need — the column grant below, not this policy, is what stops content from being
-- rewritten in place.
CREATE POLICY records_update ON mem.records FOR UPDATE TO mem_service_role
USING      (org_id = mem.org_id() AND owner_sub = mem.user_sub() AND deleted_at IS NULL)
WITH CHECK (org_id = mem.org_id() AND owner_sub = mem.user_sub());

CREATE POLICY outbox_rw ON mem.outbox FOR ALL TO mem_service_role
USING (org_id = mem.org_id()) WITH CHECK (org_id = mem.org_id());

CREATE POLICY records_owner_read ON mem.records FOR SELECT TO mem_migrator USING (true);
CREATE POLICY outbox_owner_read  ON mem.outbox  FOR SELECT TO mem_migrator USING (true);

GRANT SELECT, INSERT ON mem.records TO mem_service_role;
GRANT UPDATE (status, confirmed_at, confirmed_via, deleted_at) ON mem.records TO mem_service_role;
GRANT SELECT, INSERT ON mem.outbox TO mem_service_role;
GRANT UPDATE (applied_at) ON mem.outbox TO mem_service_role;
GRANT USAGE ON SEQUENCE mem.outbox_id_seq TO mem_service_role;

RESET ROLE;
