-- 0009 — What the Range can see in memory-db, and the two recoveries it can perform.
--
-- 0006 gave the Range its switches. This file gives it its eyes: one function per question a
-- track 9 challenge asks, each SECURITY DEFINER, owned by the migration role, bounded, returning
-- named columns. The Range composes no statement — the same rule as the core's `range` schema.
--
-- Three conventions hold throughout:
--
--   * **Seeded users by name, from a fixed list.** Where a function takes a user, it takes one of
--     the lab's seeded usernames and maps it here. An unknown name returns nothing; it never
--     becomes a subject.
--   * **Content is cut.** Every text column is truncated, and every function has a LIMIT. An
--     observation is a window, not an export.
--   * **The flag columns are computed here, from the evidence.** A value that answers a challenge
--     appears only in the state that challenge is about — a credential only if one reached the
--     context, a rule id only if nobody approved it — so a flag cannot be read before it is earned.
--
-- The two recoveries (`revoke_auto_confirmations`, and 0008's `retire_unapproved_rules`) exist
-- because restoring a setting closes a hole and does nothing about what already came through it.
-- They are the Range's only writes besides its settings, and each writes one audit event per row.

SET ROLE mem_migrator;

CREATE FUNCTION range_mem.subject_of(p_user text) RETURNS text
LANGUAGE sql IMMUTABLE
AS $$
  SELECT CASE p_user
    WHEN 'alice'   THEN 'alice-id'
    WHEN 'bob'     THEN 'bob-id'
    WHEN 'fiona'   THEN 'fiona-id'
    WHEN 'dana'    THEN 'dana-id'
    WHEN 'mallory' THEN 'mallory-id'
  END
$$;

-- ------------------------------------------------------------------------------------------------
-- The most recent context block assembled for a user, one row per item, as the service logged it.
--
-- What the model was given — not what the Range believes it was given. The service writes this log
-- in the same transaction as its audit event (0005); this reads it back.
--
-- Flag columns:
--   secret_shaped            an AWS-key-shaped string in an included item (9.1)
--   marker                   a seeded marker in an included item (9.3, 9.6)
--   outlived_email           an email address, only in a turn included after its role was lost (9.4)
--   confirmed_by_nobody      the id of an included memory the user never confirmed (9.5)
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.latest_context(p_user text)
RETURNS TABLE (
  assembled_at        timestamptz,
  item_no             integer,
  kind                text,
  source              text,
  produced_under      text,
  roles_now           text,
  included            boolean,
  content             text,
  secret_shaped       text,
  marker              text,
  outlived_email      text,
  confirmed_by_nobody text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  WITH latest AS (
    SELECT c.created_at, c.items
    FROM mem.context_log c
    WHERE c.owner_sub = range_mem.subject_of(p_user)
    ORDER BY c.created_at DESC
    LIMIT 1
  ),
  items AS (
    SELECT l.created_at, i.ordinality::integer AS item_no, i.value AS item
    FROM latest l, jsonb_array_elements(l.items) WITH ORDINALITY i
  )
  SELECT
    created_at,
    item_no,
    item->>'kind',
    CASE item->>'kind'
      WHEN 'turn'   THEN 'history turn: ' || (item->>'role')
      WHEN 'memory' THEN 'memory written by ' || (item->>'channel')
                         || coalesce(', confirmed by ' || (item->>'confirmed_via'), '')
      WHEN 'rule'   THEN 'rule proposed via ' || (item->>'channel')
                         || ', approved by ' || coalesce(item->>'decided_by', 'nobody')
    END,
    (SELECT string_agg(r, ', ') FROM jsonb_array_elements_text(item->'produced_under') r),
    (SELECT string_agg(r, ', ') FROM jsonb_array_elements_text(item->'caller_roles_now') r),
    (item->>'included')::boolean,
    left(item->>'content', 200),
    CASE WHEN (item->>'included')::boolean
         THEN substring(item->>'content' FROM 'AKIA[0-9A-Z]{16}') END,
    CASE WHEN (item->>'included')::boolean
         THEN substring(item->>'content' FROM '[A-Z]{3,}-[A-Z]{3,}-[0-9]{2,}') END,
    CASE WHEN coalesce((item->>'outlived_its_permission')::boolean, false)
         THEN substring(item->>'content' FROM '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[A-Za-z]') END,
    CASE WHEN item->>'kind' = 'memory' AND (item->>'included')::boolean
              AND item->>'confirmed_via' = 'auto'
         THEN item->>'id' END
  FROM items
  ORDER BY item_no
  LIMIT 30
$$;

-- The same block as the model reads it, line by line (9.2).
CREATE FUNCTION range_mem.latest_context_lines(p_user text)
RETURNS TABLE (line_no integer, line text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  SELECT l.ordinality::integer, left(l.line, 240)
  FROM (
    SELECT c.rendered FROM mem.context_log c
    WHERE c.owner_sub = range_mem.subject_of(p_user)
    ORDER BY c.created_at DESC
    LIMIT 1
  ) latest,
  regexp_split_to_table(latest.rendered, E'\n') WITH ORDINALITY AS l(line, ordinality)
  ORDER BY 1
  LIMIT 40
$$;

-- ------------------------------------------------------------------------------------------------
-- 9.3: bob's most recent attempt to read alice's seeded session, and — only if the service allowed
-- it — what that session holds. The service's audit event decides whether content is shown, so
-- this reports what happened, not what a policy would have said.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.bob_reads_alice_transcript()
RETURNS TABLE (attempted_at timestamptz, decision text, reason text, seq integer, role text,
               content text, marker text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  WITH attempt AS (
    SELECT a.occurred_at, a.decision, a.reason
    FROM mem.audit_events a
    WHERE a.action = 'transcript.read'
      AND a.actor_sub = 'bob-id'
      AND a.resource_id = '9a000000-0000-4000-8000-00000000a1ce'
    ORDER BY a.occurred_at DESC
    LIMIT 1
  )
  SELECT att.occurred_at, att.decision, att.reason, t.seq, t.role, left(t.content, 200),
         substring(t.content FROM '[A-Z]{3,}-[A-Z]{3,}-[0-9]{2,}')
  FROM attempt att
  LEFT JOIN mem.turns t
    ON att.decision = 'allowed' AND t.session_id = '9a000000-0000-4000-8000-00000000a1ce'
  ORDER BY t.seq NULLS FIRST
  LIMIT 20
$$;

-- ------------------------------------------------------------------------------------------------
-- 9.7: cedar's rules, newest first. `active_without_approval` carries a rule's id only when it is
-- being obeyed and nobody but its proposer ever looked at it.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.rule_states()
RETURNS TABLE (created_at timestamptz, rule_id uuid, state text, proposed_by text, channel text,
               decided_by text, retired_by text, rule_text text, active_without_approval text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  SELECT r.created_at, r.id, r.state, r.proposed_by, r.proposed_channel, r.decided_by,
         r.retired_by, left(r.text, 160),
         CASE WHEN r.state = 'active' AND r.decided_by IS NULL THEN r.id::text END
  FROM mem.rules r
  WHERE r.org_id = '11111111-1111-1111-1111-111111111111'
  ORDER BY r.created_at DESC
  LIMIT 12
$$;

-- ------------------------------------------------------------------------------------------------
-- 9.8: alice's three most recently forgotten memories, and every record derived from each — with
-- whether each still lives. `survivor` carries the id of a derived record that outlived the forget.
--
-- Three, not one, because the observation runs a fresh forget every time it is run — including when
-- a flag is checked — and a survivor found a moment ago must still be there to be named.
--
-- The vector store's copies are checked by the Range itself, with its read-only tokens, using the
-- ids this returns: the database cannot see into Qdrant, and the question is where copies are.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.remaining_copies()
RETURNS TABLE (record_id uuid, relation text, state text, content text, survivor text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  WITH RECURSIVE target AS (
    SELECT r.id, r.deleted_at FROM mem.records r
    WHERE r.owner_sub = 'alice-id' AND r.derived_from IS NULL AND r.deleted_at IS NOT NULL
    ORDER BY r.deleted_at DESC
    LIMIT 3
  ),
  tree AS (
    SELECT r.id, 0 AS depth, t.deleted_at AS forgotten_at
    FROM mem.records r JOIN target t ON r.id = t.id
    UNION ALL
    SELECT r.id, tree.depth + 1, tree.forgotten_at
    FROM mem.records r JOIN tree ON r.derived_from = tree.id
    WHERE tree.depth < 8
  )
  SELECT r.id,
         CASE WHEN tree.depth = 0 THEN 'the memory that was forgotten'
              ELSE 'derived from it (depth ' || tree.depth || ')' END,
         CASE WHEN r.deleted_at IS NULL THEN 'still live' ELSE 'forgotten' END,
         left(r.content, 160),
         CASE WHEN tree.depth > 0 AND r.deleted_at IS NULL THEN r.id::text END
  FROM tree JOIN mem.records r ON r.id = tree.id
  ORDER BY tree.forgotten_at DESC, tree.depth
  LIMIT 20
$$;

-- 9.5: a user's most recent memories, with who wrote each and whether — and how — it was confirmed.
CREATE FUNCTION range_mem.records_of(p_user text)
RETURNS TABLE (created_at timestamptz, record_id uuid, channel text, status text,
               confirmed_via text, content text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
  SELECT r.created_at, r.id, r.channel, r.status, r.confirmed_via, left(r.content, 160)
  FROM mem.records r
  WHERE r.owner_sub = range_mem.subject_of(p_user) AND r.deleted_at IS NULL
  ORDER BY r.created_at DESC
  LIMIT 10
$$;

-- Where the outbox stands: an operation written to memory-db but not yet applied to the vectors.
CREATE FUNCTION range_mem.outbox_state()
RETURNS TABLE (op text, pending bigint, oldest timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, pg_temp
AS $$
  SELECT o.op, count(*), min(o.created_at)
  FROM mem.outbox o WHERE o.applied_at IS NULL
  GROUP BY o.op ORDER BY o.op
  LIMIT 4
$$;

-- ------------------------------------------------------------------------------------------------
-- The Range's recovery for 9.5: every memory born confirmed because the setting said so goes back
-- to unconfirmed, to wait for the person it belongs to. Nothing is deleted — the user may still
-- confirm it — and nothing a user confirmed is touched.
-- ------------------------------------------------------------------------------------------------
CREATE FUNCTION range_mem.revoke_auto_confirmations() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = mem, range_mem, pg_temp
AS $$
DECLARE
  revoked integer := 0;
  r record;
BEGIN
  FOR r IN
    UPDATE mem.records SET status = 'unconfirmed', confirmed_at = NULL, confirmed_via = NULL
    WHERE confirmed_via = 'auto' AND deleted_at IS NULL
    RETURNING id, org_id
  LOOP
    revoked := revoked + 1;
    INSERT INTO mem.audit_events (request_id, actor_type, actor_sub, org_id, action, resource_type,
                                  resource_id, decision, reason)
    VALUES ('range-' || gen_random_uuid(), 'range', 'the-range', r.org_id, 'memory.unconfirm',
            'memory', r.id::text, 'succeeded', 'revoked:auto_confirmed');
  END LOOP;
  RETURN revoked;
END
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'range_mem.subject_of(text)',
    'range_mem.latest_context(text)',
    'range_mem.latest_context_lines(text)',
    'range_mem.bob_reads_alice_transcript()',
    'range_mem.rule_states()',
    'range_mem.remaining_copies()',
    'range_mem.records_of(text)',
    'range_mem.outbox_state()',
    'range_mem.revoke_auto_confirmations()'
  ] LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
  END LOOP;
END
$$;

GRANT EXECUTE ON FUNCTION range_mem.latest_context(text)          TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.latest_context_lines(text)    TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.bob_reads_alice_transcript()  TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.rule_states()                 TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.remaining_copies()            TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.records_of(text)              TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.outbox_state()                TO mem_range_role;
GRANT EXECUTE ON FUNCTION range_mem.revoke_auto_confirmations()   TO mem_range_role;

RESET ROLE;
