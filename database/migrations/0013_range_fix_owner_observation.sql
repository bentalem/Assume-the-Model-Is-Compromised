-- 0013 — Two corrections to the 2.1 observations, both found by running them.
--
-- 1. The owner-side policy was USING (true).
--
--    That made the owner observation return every tenant's rows in *every* configuration,
--    including the correct one. The flag for challenge 2.1 is northwind's order total, and it was
--    readable while both mutations probed `correct` — a flag obtainable unarmed, which is the one
--    property the brief says a flag must never have. The challenge would have been solvable by
--    pressing a button before touching anything.
--
--    The fix is not a narrower grant; it is the right policy. The owner gets the *same tenant
--    condition* as everyone else, so the demonstration becomes real:
--
--        FORCE on   → the owner is subject to the policy  → cedar rows only
--        FORCE off  → the owner is exempt                 → every tenant's rows
--
--    Which is the mechanism the challenge teaches, rather than a staged version of it.
--
-- 2. `observe_orders_as_api` is removed.
--
--    It used SET LOCAL ROLE inside a SECURITY DEFINER function, which PostgreSQL forbids outright:
--    "cannot set parameter role within security-definer function". There is a workaround — own the
--    function as sp_api_role — and it is the wrong thing to do, because it would hand a runtime
--    role something to own in a lab whose fifth build rule is that runtime roles own nothing.
--
--    A control group is not worth breaking a rule for. The contrast is carried by the truth table
--    in Stage 01 and by the catalogue observation, which is also the query a learner should leave
--    with.

BEGIN;

SET ROLE sp_migrator_role;

DROP POLICY orders_migrator_read ON app.orders;

CREATE POLICY orders_migrator_read ON app.orders FOR SELECT TO sp_migrator_role
USING (organization_id = app.current_org());

DROP FUNCTION IF EXISTS range.observe_orders_as_api();

INSERT INTO app.schema_migrations (version) VALUES ('0013_range_fix_owner_observation');

RESET ROLE;
COMMIT;
