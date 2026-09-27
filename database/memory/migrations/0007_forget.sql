-- 0007 — Forgetting, through one narrow function rather than a plain UPDATE.
--
-- The first version of `forget` was an UPDATE setting `deleted_at`, and the store refused it:
--
--     ERROR: new row violates row-level security policy for table "records"
--
-- That is PostgreSQL working as documented, and it is a trap worth knowing. When an UPDATE reads
-- columns in its WHERE clause, the new row must still satisfy the table's SELECT policy — so that
-- nobody can update a row into a state they are no longer allowed to see. `records_read` hides
-- forgotten rows (`deleted_at IS NULL`). A soft delete therefore produces a row its author may not
-- see, and every soft delete fails. Anyone combining soft deletion with row-level security meets
-- this.
--
-- There were two ways out, and the choice is the lesson:
--
--   * Drop `deleted_at IS NULL` from the read policy, and filter forgotten rows in every query the
--     service makes. That works, and it moves "a forgotten memory is never read again" from the
--     store to the application — the exact kind of control this track teaches people not to leave
--     to a filter somebody might forget.
--   * Keep the read policy, and forget through a SECURITY DEFINER function that performs one
--     update, on the caller's own live records, identified by the caller's own context.
--
-- This file does the second. The service loses its UPDATE on `deleted_at`; forgetting is now a
-- call to this function or nothing.

SET ROLE mem_migrator;

-- The owner may update records, so that the function (which runs as the owner) can. FORCE applies
-- to the owner too.
CREATE POLICY records_owner_update ON mem.records FOR UPDATE TO mem_migrator
USING (true) WITH CHECK (true);

CREATE FUNCTION mem.forget_records(p_ids uuid[]) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = mem, pg_temp
AS $$
DECLARE
  changed integer;
BEGIN
  -- The caller's identity comes from the transaction-local context the service set, exactly as the
  -- policies read it. Nothing about whose records these are is taken from the arguments: a list of
  -- ids naming somebody else's memories changes nothing, because none of them match.
  IF mem.user_sub() IS NULL OR mem.org_id() IS NULL THEN
    RAISE EXCEPTION 'forget_records called with no request context';
  END IF;

  UPDATE mem.records
     SET deleted_at = now()
   WHERE id = ANY (p_ids)
     AND org_id = mem.org_id()
     AND owner_sub = mem.user_sub()
     AND deleted_at IS NULL;
  GET DIAGNOSTICS changed = ROW_COUNT;
  RETURN changed;
END
$$;

REVOKE ALL ON FUNCTION mem.forget_records(uuid[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION mem.forget_records(uuid[]) TO mem_service_role;

-- The direct route is closed, so forgetting has exactly one implementation.
REVOKE UPDATE (deleted_at) ON mem.records FROM mem_service_role;

RESET ROLE;
