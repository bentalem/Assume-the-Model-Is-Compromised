-- 0005 — The context log: every context block, exactly as it was delivered.
--
-- Context is the only thing a model ever sees. Every kind of memory ends up there, and that is
-- where the damage happens — so the memory layer records, for every block it assembles, the text
-- it produced and the provenance of every item in it.
--
-- This is a real control, not a teaching convenience. "Why did the agent believe this?" is
-- unanswerable without it: the model's answer is a narration built from a context nobody kept, and
-- challenge 7.2 is about how little a narration is worth. With it, the question has a row.
--
-- It is also why the Range never needs a probe to return content. Probes keep their rule —
-- status, error code, field names, never values — and the content a challenge shows is read from
-- this table by a bounded observation.

SET ROLE mem_migrator;

CREATE TABLE mem.context_log (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id text NOT NULL,
  org_id     uuid NOT NULL,
  owner_sub  text NOT NULL,
  query      text NOT NULL CHECK (length(query) <= 500),
  -- The block as the model would read it.
  rendered   text NOT NULL,
  -- One entry per item: its kind, its source, and — for anything omitted — why.
  items      jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX context_owner ON mem.context_log (org_id, owner_sub, created_at DESC);

ALTER TABLE mem.context_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.context_log FORCE  ROW LEVEL SECURITY;

CREATE POLICY context_insert ON mem.context_log FOR INSERT TO mem_service_role
WITH CHECK (org_id = mem.org_id() AND owner_sub = mem.user_sub());

CREATE POLICY context_read ON mem.context_log FOR SELECT TO mem_service_role
USING (org_id = mem.org_id() AND owner_sub = mem.user_sub());

CREATE POLICY context_owner_read ON mem.context_log FOR SELECT TO mem_migrator USING (true);

GRANT SELECT, INSERT ON mem.context_log TO mem_service_role;

RESET ROLE;
