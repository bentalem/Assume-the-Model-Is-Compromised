-- 0010 — What a restored setting leaves behind, counted.
--
-- Three of track 9's settings let something through that outlives the setting: a memory born
-- confirmed (9.5), a rule that activated itself (9.7), a summary that survived its source's forget
-- (9.8). The Range's rule is that a probe reports the system, not the switch — so for these three the
-- probe asks two questions, "is the setting secure?" and "is anything it let through still there?",
-- and reports `correct` only when both answers are yes. A reset then restores until both hold.
--
-- Counts only. What the leftovers are is what the observations show.

SET ROLE mem_migrator;

CREATE FUNCTION range_mem.leftovers()
RETURNS TABLE (kind text, remaining bigint)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = mem, pg_temp
AS $$
  SELECT 'auto_confirmed_memories',
         (SELECT count(*) FROM mem.records WHERE confirmed_via = 'auto' AND deleted_at IS NULL)
  UNION ALL
  SELECT 'rules_active_without_approval',
         (SELECT count(*) FROM mem.rules WHERE state = 'active' AND decided_by IS NULL)
  UNION ALL
  SELECT 'derivations_of_forgotten_memories',
         (SELECT count(*) FROM mem.records r JOIN mem.records p ON r.derived_from = p.id
          WHERE p.deleted_at IS NOT NULL AND r.deleted_at IS NULL)
$$;

REVOKE ALL ON FUNCTION range_mem.leftovers() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range_mem.leftovers() TO mem_range_role;

RESET ROLE;
