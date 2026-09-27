-- 0002 — Session history.
--
-- History is the memory everybody forgets they have. Every turn of a conversation is kept and
-- replayed into context on the next turn, which makes it a second copy of everything sensitive the
-- agent ever saw — a copy with its own access question, separate from the question of whether the
-- agent was allowed to see the original.
--
-- Two things in this file carry lessons:
--
--   * The read policy has one clause that is off by default: managers reading their organisation's
--     transcripts "for quality review". Real deployments ship exactly that. The policy text never
--     changes; `history.org_readable` in mem.settings decides whether the clause can be true.
--     Challenge 9.3 arms it.
--
--   * Every turn records `authz` — the roles the caller held when the turn was written, captured by
--     the service from the verified principal, never from the request. Replaying a turn into
--     context later re-checks that the caller still holds them. Challenge 9.4 turns that off.

SET ROLE mem_migrator;

CREATE TABLE mem.sessions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL,
  owner_sub  text NOT NULL,
  title      text CHECK (title IS NULL OR length(title) <= 200),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX sessions_owner ON mem.sessions (org_id, owner_sub, created_at DESC);

CREATE TABLE mem.turns (
  id         bigserial PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES mem.sessions(id),
  org_id     uuid NOT NULL,
  owner_sub  text NOT NULL,
  seq        integer NOT NULL CHECK (seq >= 1),
  role       text NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
  content    text NOT NULL CHECK (length(content) BETWEEN 1 AND 8000),
  -- The authorisation the content was produced under: {"roles": [...], "at": "..."}. Captured by
  -- the service from the verified principal at write time. Not a claim the caller made.
  authz      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, seq)
);

CREATE INDEX turns_session ON mem.turns (session_id, seq);

ALTER TABLE mem.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.sessions FORCE  ROW LEVEL SECURITY;
ALTER TABLE mem.turns    ENABLE ROW LEVEL SECURITY;
ALTER TABLE mem.turns    FORCE  ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------------------------
-- Read: your own history, always. Your organisation's, only if the setting is on AND you are a
-- manager in it. The same text in both tables, so a session and its turns can never disagree
-- about who may see them.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY sessions_read ON mem.sessions FOR SELECT TO mem_service_role
USING (
  org_id = mem.org_id()
  AND (
    owner_sub = mem.user_sub()
    OR (mem.setting('history.org_readable') = 'true' AND mem.has_role('support_manager'))
  )
);

CREATE POLICY turns_read ON mem.turns FOR SELECT TO mem_service_role
USING (
  org_id = mem.org_id()
  AND (
    owner_sub = mem.user_sub()
    OR (mem.setting('history.org_readable') = 'true' AND mem.has_role('support_manager'))
  )
);

-- ------------------------------------------------------------------------------------------------
-- Write: into your own session, in your own organisation, and nowhere else. The turn check also
-- requires the session to be yours, so a manager who can *read* a colleague's session under the
-- quality-review setting still cannot append to it.
-- ------------------------------------------------------------------------------------------------
CREATE POLICY sessions_insert ON mem.sessions FOR INSERT TO mem_service_role
WITH CHECK (org_id = mem.org_id() AND owner_sub = mem.user_sub());

CREATE POLICY turns_insert ON mem.turns FOR INSERT TO mem_service_role
WITH CHECK (
  org_id = mem.org_id()
  AND owner_sub = mem.user_sub()
  AND EXISTS (
    SELECT 1 FROM mem.sessions s
    WHERE s.id = session_id AND s.owner_sub = mem.user_sub() AND s.org_id = mem.org_id()
  )
);

-- The owner reads both, for the Range's bounded observations.
CREATE POLICY sessions_owner_read ON mem.sessions FOR SELECT TO mem_migrator USING (true);
CREATE POLICY turns_owner_read    ON mem.turns    FOR SELECT TO mem_migrator USING (true);

GRANT SELECT, INSERT ON mem.sessions TO mem_service_role;
GRANT SELECT, INSERT ON mem.turns    TO mem_service_role;
GRANT USAGE ON SEQUENCE mem.turns_id_seq TO mem_service_role;

RESET ROLE;
