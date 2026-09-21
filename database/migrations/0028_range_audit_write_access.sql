-- 0028 — The Range: is the trail actually append-only, for challenge 7.1.
--
-- 7.1's Stage 03 ends on a claim with two halves. No runtime role can amend a written row, because
-- sp_api_role and sp_worker_role hold INSERT and nothing else. And the owner, which does hold UPDATE
-- and DELETE, changes nothing either, because FORCE ROW LEVEL SECURITY applies the table's policies
-- to the owner as well and there is no UPDATE policy for anyone — so the statement is permitted,
-- matches no rows, and reports `UPDATE 0`.
--
-- Both halves are statements about the catalogue, and until now the challenge asked a learner to
-- take them from the prose. That is the wrong way round in the challenge whose own lesson is that a
-- schema is a promise and a query is evidence. This function is the query.
--
-- It reads pg_class, its ACL and pg_policies. It takes no argument, names one table in its body, and
-- cannot write anything — the same shape as range.all_table_security() and range.catalogue_unforced().
--
-- Two things it deliberately reports rather than hides:
--
--   * PUBLIC, if a grant ever reaches it. An append-only claim that is true only because nobody has
--     run a GRANT yet is worth seeing go false.
--   * TRUNCATE, which is a table-level command that row-level security does not filter. The owner
--     holds it and no policy would stop it, which is the concrete form of Stage 03's own concession
--     that this property is made of grants and protects the record from the application rather than
--     from anyone who can change grants.

BEGIN;

SET ROLE sp_migrator_role;

CREATE FUNCTION range.audit_write_access()
RETURNS TABLE (command text, granted_to text, policies text, effect text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  WITH target AS (
    SELECT coalesce(c.relacl, acldefault('r'::"char", c.relowner)) AS acl,
           c.relforcerowsecurity                                   AS forced
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'app' AND c.relname = 'audit_events'
  ),
  commands (ord, command, row_level) AS (
    VALUES (1, 'SELECT', true), (2, 'INSERT', true), (3, 'UPDATE', true),
           (4, 'DELETE', true), (5, 'TRUNCATE', false)
  ),
  held AS (
    SELECT a.privilege_type::text AS command,
           CASE WHEN a.grantee = 0 THEN 'PUBLIC'
                ELSE pg_get_userbyid(a.grantee)::text END AS role_name
    FROM target t, aclexplode(t.acl) a
  ),
  matched AS (
    SELECT c.command AS command, p.policyname::text AS name
    FROM commands c
    JOIN pg_policies p
      ON p.schemaname = 'app'
     AND p.tablename = 'audit_events'
     AND (p.cmd = 'ALL' OR p.cmd = c.command)
    WHERE c.row_level
  )
  SELECT c.command::text,
         coalesce(
           (SELECT string_agg(DISTINCT h.role_name, ', ' ORDER BY h.role_name)
            FROM held h WHERE h.command = c.command),
           'nobody')::text,
         CASE
           WHEN NOT c.row_level THEN '(row security does not filter this command)'
           ELSE coalesce(
             (SELECT string_agg(m.name, ', ' ORDER BY m.name)
              FROM matched m WHERE m.command = c.command),
             'none')
         END::text,
         CASE
           WHEN NOT c.row_level THEN
             'whoever holds the grant can run it; no policy is consulted'
           WHEN NOT EXISTS (SELECT 1 FROM matched m WHERE m.command = c.command) THEN
             CASE WHEN t.forced
                  THEN 'permitted, matched by no policy — and FORCE applies that to the owner too, '
                       || 'so the statement succeeds and changes 0 rows'
                  ELSE 'permitted, matched by no policy — and row security is not forced, so the '
                       || 'owner is exempt and rows do change'
             END
           ELSE 'permitted for the roles the policy names, and only for the rows it matches'
         END::text
  FROM commands c, target t
  ORDER BY c.ord;
$$;

ALTER FUNCTION range.audit_write_access() OWNER TO sp_migrator_role;
REVOKE ALL ON FUNCTION range.audit_write_access() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION range.audit_write_access() TO sp_range_role;

INSERT INTO app.schema_migrations (version) VALUES ('0028_range_audit_write_access');

RESET ROLE;
COMMIT;
