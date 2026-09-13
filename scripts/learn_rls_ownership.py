"""Module 4 — the row-level security failure that survives code review.

PostgreSQL exempts a table's **owner** from its own row policies unless FORCE is set. An application
that connects as the role which created the tables therefore gets no filtering at all, while the
policies sit there — correctly written, present in every schema dump, doing nothing.

Nothing in a code review shows this. The policy is right. The query is right. The only wrong thing is
which database role holds the connection, and that lives in a config file somewhere else.

This builds a throwaway role and schema, measures three configurations, and drops both. It never
touches app.* and never grants ownership to sp_api_role — rule 5 holds even in a demonstration.

    python scripts/learn_rls_ownership.py demo     run the three configurations, then clean up
    python scripts/learn_rls_ownership.py clean    remove the demo objects if a run was interrupted
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# A stand-in for "the application's database role". Deliberately not sp_api_role: giving a runtime
# role ownership would break build rule 5, and a demonstration is not a reason to break a rule.
DEMO_ROLE = "rls_demo_app"

CEDAR = "11111111-1111-1111-1111-111111111111"
NORTHWIND = "22222222-2222-2222-2222-222222222222"

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"
)

DROP_ROLE = (
    "DO $do$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_demo_app') THEN "
    "EXECUTE 'DROP ROLE rls_demo_app'; END IF; END $do$;"
)


def psql(statement: str, role: str = "supportpilot_admin") -> str:
    password = (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}", "postgres",
         "psql", "-U", role, "-d", "supportpilot", "-tAX", "-v", "ON_ERROR_STOP=1", "-c", statement],
        cwd=REPO, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit(f"\n  {RED}{(proc.stderr or proc.stdout).strip()[:400]}{RESET}\n")
    return proc.stdout.strip()


def flags() -> str:
    """enabled/forced, read from the catalogue rather than from what we believe we set."""
    return psql(
        "SELECT c.relrowsecurity::text || ' / ' || c.relforcerowsecurity::text "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'rls_demo' AND c.relname = 'orders'"
    )


def visible_rows() -> tuple[int, int]:
    """Read the demo table as the demo application role, with cedar as the request tenant."""
    output = psql(
        "BEGIN; "
        f"SELECT set_config('app.organization_id', '{CEDAR}', true); "
        "SELECT tenant FROM rls_demo.orders; "
        "COMMIT;",
        role=DEMO_ROLE,
    )
    rows = [line.strip() for line in output.splitlines()]
    return sum(1 for r in rows if r == "cedar"), sum(1 for r in rows if r == "northwind")


def report(note: str) -> None:
    cedar, foreign = visible_rows()
    verdict = (
        f"{RED}LEAK — {foreign} row(s) belonging to another tenant{RESET}" if foreign
        else f"{GREEN}filtered — this tenant only{RESET}"
    )
    print(f"  rows visible to a cedar request:  cedar {cedar}   northwind {foreign}   {verdict}")
    print(f"  {GREY}{note}{RESET}")
    print()


def cmd_clean() -> None:
    psql("DROP SCHEMA IF EXISTS rls_demo CASCADE")
    psql(DROP_ROLE)
    remaining = psql(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'rls_demo'"
    )
    role_left = psql("SELECT count(*) FROM pg_roles WHERE rolname = 'rls_demo_app'")
    print(f"  {GREEN}demo role and schema removed{RESET}   "
          f"{GREY}objects remaining: {remaining}   roles remaining: {role_left}{RESET}")
    print()


def cmd_demo() -> None:
    print()
    print(f"{BOLD}Row-level security — the same policy in three configurations{RESET}")
    print("=" * 78)
    print(f"  {GREY}A throwaway role and schema. app.* is not touched; sp_api_role is not touched.{RESET}")
    print()

    psql("DROP SCHEMA IF EXISTS rls_demo CASCADE")
    psql(DROP_ROLE)
    psql(f"CREATE ROLE {DEMO_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS")
    psql(f"CREATE SCHEMA rls_demo AUTHORIZATION {DEMO_ROLE}")

    # Created *by* the demo role, so the demo role owns it. That is the whole scenario: the
    # application's database user is also the user that ran the migrations.
    psql(
        "CREATE TABLE rls_demo.orders ("
        "  id serial PRIMARY KEY, tenant text NOT NULL, organization_id uuid NOT NULL)",
        role=DEMO_ROLE,
    )
    psql(
        "INSERT INTO rls_demo.orders (tenant, organization_id) VALUES "
        f"('cedar', '{CEDAR}'), ('cedar', '{CEDAR}'), ('northwind', '{NORTHWIND}')",
        role=DEMO_ROLE,
    )

    owner = psql(
        "SELECT pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'rls_demo' AND c.relname = 'orders'"
    )
    bypass = psql(f"SELECT rolbypassrls::text FROM pg_roles WHERE rolname = '{DEMO_ROLE}'")
    print(f"  table owner        {BOLD}{owner}{RESET}")
    print(f"  BYPASSRLS          {bypass}   {GREY}(not a superuser, no bypass attribute){RESET}")
    print(f"  contents           {GREY}3 rows — 2 cedar, 1 northwind{RESET}")
    print()

    # -------------------------------------------------------------------------------------------
    print(f"{BOLD}1. No row-level security{RESET}")
    print(f"   {GREY}enabled / forced = {flags()}{RESET}")
    report("Expected. Nothing is filtering anything.")

    # -------------------------------------------------------------------------------------------
    psql(
        "ALTER TABLE rls_demo.orders ENABLE ROW LEVEL SECURITY; "
        f"CREATE POLICY tenant_read ON rls_demo.orders FOR SELECT TO {DEMO_ROLE} "
        "USING (organization_id = nullif(current_setting('app.organization_id', true), '')::uuid)",
        role=DEMO_ROLE,
    )
    print(f"{BOLD}2. ENABLE ROW LEVEL SECURITY, with a correct policy{RESET}")
    print(f"   {GREY}enabled / forced = {flags()}{RESET}")
    print(f"   {GREY}USING (organization_id = the tenant set on this transaction){RESET}")
    report("The policy exists, is correct, and names this exact role.")
    print(f"  {YELLOW}This is the configuration that passes review.{RESET}")
    print(f"  {GREY}The policy is right. The query is right. The connection belongs to the owner,{RESET}")
    print(f"  {GREY}and PostgreSQL exempts an owner from its own table's policies.{RESET}")
    print()

    # -------------------------------------------------------------------------------------------
    psql("ALTER TABLE rls_demo.orders FORCE ROW LEVEL SECURITY", role=DEMO_ROLE)
    print(f"{BOLD}3. The same table and the same policy, plus FORCE{RESET}")
    print(f"   {GREY}enabled / forced = {flags()}   nothing else changed{RESET}")
    report("One keyword. No application change, no policy change.")

    # -------------------------------------------------------------------------------------------
    print(f"{BOLD}4. And with no tenant set at all{RESET}")
    empty = psql("SELECT count(*) FROM rls_demo.orders", role=DEMO_ROLE).splitlines()[0].strip()
    print(f"  rows visible with app.organization_id unset:  {GREEN}{empty}{RESET}")
    print(f"  {GREY}NULL = NULL is NULL, not TRUE. Forgetting the context returns nothing —{RESET}")
    print(f"  {GREY}it does not return everything. That asymmetry is the whole design.{RESET}")
    print()

    # -------------------------------------------------------------------------------------------
    print(f"{BOLD}What the real tables look like{RESET}")
    real = psql(
        "SELECT rpad(c.relname, 18) || rpad(pg_get_userbyid(c.relowner), 18) "
        "|| rpad(c.relrowsecurity::text, 9) || c.relforcerowsecurity::text "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'app' AND c.relkind = 'r' "
        "AND c.relname IN ('orders', 'customers', 'tickets') ORDER BY c.relname"
    )
    print(f"  {GREY}{'table':<18}{'owner':<18}{'enabled':<9}forced{RESET}")
    for line in real.splitlines():
        print(f"  {GREEN}{line}{RESET}")
    print()
    print(f"  {GREY}Two independent reasons the leak above cannot happen here: the runtime role does{RESET}")
    print(f"  {GREY}not own these tables, and FORCE is set anyway. Either alone would be enough —{RESET}")
    print(f"  {GREY}which is exactly why both are there.{RESET}")
    print()

    cmd_clean()

    print(f"{BOLD}What to ask a client{RESET}")
    print("=" * 78)
    print(f"  {GREY}Not \"do you use row-level security\". The answer is always yes.{RESET}")
    print()
    print("    1. Which database role does the application connect as?")
    print("    2. Does that role own the tables?")
    print("    3. Is FORCE set, or only ENABLE?")
    print("    4. Does that role have BYPASSRLS, or SUPERUSER?")
    print()
    print(f"  {GREY}One query answers the first three. Worth carrying into a review:{RESET}")
    print()
    print(f"  {GREY}  SELECT c.relname, pg_get_userbyid(c.relowner) AS owner,{RESET}")
    print(f"  {GREY}         c.relrowsecurity AS enabled, c.relforcerowsecurity AS forced{RESET}")
    print(f"  {GREY}  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace{RESET}")
    print(f"  {GREY}  WHERE n.nspname = 'app' AND c.relkind = 'r';{RESET}")
    print()
    print(f"  {GREY}  SELECT rolname, rolsuper, rolbypassrls FROM pg_roles;{RESET}")
    print()


COMMANDS = {"demo": cmd_demo, "clean": cmd_clean}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    COMMANDS[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
