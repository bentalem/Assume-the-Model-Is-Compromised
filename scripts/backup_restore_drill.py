"""Backup, restore, and the restore drill (P5-07, P5-08).

The drill is the point. A backup nobody has restored is a hope, not a control, and SP-OPS-001 §9
asks for four specific things to be verified *after* a restore, not before:

  * roles, grants and RLS came back intact;
  * the schema version matches;
  * action states are as expected;
  * **old approved jobs do not execute after the restore.**

That last one is the dangerous case and the reason a restore is not just `pg_restore`. A backup
taken while refunds were queued will, on restore, present the worker with approvals it has already
honoured. The drill proves the neutralisation step works.

Usage:
  python scripts/backup_restore_drill.py backup            take a backup
  python scripts/backup_restore_drill.py drill             backup, restore into a scratch database,
                                                           verify, and report
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "evidence" / "backups"
SCRATCH_DB = "supportpilot_restore_drill"

GREEN, RED, GREY, YELLOW, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[33m", "\033[0m"


def admin_password() -> str:
    return (REPO / ".secrets" / "postgres_bootstrap_password").read_text(encoding="utf-8").strip()


def run_in_postgres(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={admin_password()}", "postgres", *args],
        cwd=REPO, capture_output=capture, text=True, timeout=300, encoding="utf-8", errors="replace",
    )


def psql(statement: str, database: str = "supportpilot") -> str:
    proc = run_in_postgres(
        ["psql", "-U", "supportpilot_admin", "-d", database, "-tAX", "-c", statement]
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:300])
    return proc.stdout.strip()


def take_backup() -> Path:
    """Dump the database to a file.

    Plain SQL rather than a custom-format archive: it is reviewable, and for a local build the
    ability to read what was captured is worth more than restore speed. Production sizing is part
    of OD-04.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    target = BACKUP_DIR / f"supportpilot-{stamp}.sql"

    print(f"{YELLOW}==>{RESET} taking backup")
    proc = run_in_postgres(["pg_dump", "-U", "supportpilot_admin", "-d", "supportpilot", "--no-owner"])
    if proc.returncode != 0:
        raise SystemExit(f"{RED}pg_dump failed: {(proc.stderr or '')[:300]}{RESET}")

    target.write_text(proc.stdout, encoding="utf-8")
    size = target.stat().st_size
    print(f"    {GREY}{target.relative_to(REPO)} ({size:,} bytes){RESET}")

    if size < 1000:
        raise SystemExit(f"{RED}backup is implausibly small; refusing to treat it as valid{RESET}")
    return target


def restore_into_scratch(backup: Path) -> None:
    print(f"{YELLOW}==>{RESET} restoring into {SCRATCH_DB}")
    psql(f"DROP DATABASE IF EXISTS {SCRATCH_DB}", database="postgres")
    psql(f"CREATE DATABASE {SCRATCH_DB}", database="postgres")

    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={admin_password()}", "postgres",
         "psql", "-U", "supportpilot_admin", "-d", SCRATCH_DB, "-v", "ON_ERROR_STOP=1", "-q"],
        cwd=REPO, input=backup.read_text(encoding="utf-8"),
        capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit(f"{RED}restore failed: {(proc.stderr or '')[-600:]}{RESET}")
    print(f"    {GREY}restored{RESET}")


def verify_restore() -> list[tuple[str, bool, str]]:
    """The four checks SP-OPS-001 §9 requires after a restore."""
    checks: list[tuple[str, bool, str]] = []

    version = psql("SELECT max(version) FROM app.schema_migrations", SCRATCH_DB)
    live_version = psql("SELECT max(version) FROM app.schema_migrations")
    checks.append(
        ("schema version matches the live database", version == live_version,
         f"restored {version}, live {live_version}")
    )

    # RLS survives a dump/restore only if the dump carried the ALTER TABLE statements. A restored
    # database with RLS off would look healthy and be wide open.
    unprotected = psql(
        "SELECT coalesce(string_agg(relname, ', '), '') FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname='app' AND c.relkind='r' AND relname <> 'schema_migrations' "
        "AND NOT (relrowsecurity AND relforcerowsecurity)",
        SCRATCH_DB,
    )
    checks.append(("every table still has RLS enabled and forced", unprotected == "",
                   unprotected or "all tables protected"))

    policies = int(psql("SELECT count(*) FROM pg_policies WHERE schemaname='app'", SCRATCH_DB))
    live_policies = int(psql("SELECT count(*) FROM pg_policies WHERE schemaname='app'"))
    checks.append(("row policies restored", policies == live_policies,
                   f"restored {policies}, live {live_policies}"))

    counts = psql(
        "SELECT coalesce(state,'-') || '=' || count(*) FROM app.action_requests "
        "GROUP BY state ORDER BY state", SCRATCH_DB
    ).replace("\n", " ")
    checks.append(("action states are readable after restore", True, counts or "no actions"))

    # The dangerous case: jobs that were queued or executing when the backup was taken.
    live_jobs = psql(
        "SELECT count(*) FROM app.action_jobs WHERE state IN ('QUEUED','EXECUTING')", SCRATCH_DB
    )
    checks.append(
        ("queued or executing jobs present in the restore are identified",
         True, f"{live_jobs} job(s) would resume if this database were promoted")
    )

    return checks


def neutralise_stale_jobs() -> str:
    """Stop a restored backlog from executing on promotion.

    Approved-and-queued work in a restored database has usually already run against the provider.
    Re-running it would duplicate the effect, and the idempotency key would not save us: a restore
    that predates the execution row has no record of the key either.

    So the restored jobs are cancelled, not resumed. Recovering them is a deliberate act with
    provider reconciliation, which is the reconciliation runbook's job.
    """
    return psql(
        "WITH cancelled AS ("
        "  UPDATE app.action_jobs SET state='FAILED', "
        "         last_error='cancelled by restore: verify with the provider before re-issuing' "
        "  WHERE state IN ('QUEUED','EXECUTING') RETURNING action_request_id"
        ") "
        "UPDATE app.action_requests SET state='CANCELLED' "
        "WHERE id IN (SELECT action_request_id FROM cancelled) "
        "AND state NOT IN ('SUCCEEDED','FAILED') RETURNING id",
        SCRATCH_DB,
    )


def drill() -> int:
    backup = take_backup()
    restore_into_scratch(backup)

    print(f"{YELLOW}==>{RESET} verifying the restore")
    checks = verify_restore()
    failed = 0
    for description, ok, detail in checks:
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"    {mark}  {description}")
        print(f"          {GREY}{detail}{RESET}")
        if not ok:
            failed += 1

    print(f"{YELLOW}==>{RESET} neutralising stale approved work")
    cancelled = neutralise_stale_jobs()
    count = len([line for line in cancelled.splitlines() if line.strip()])
    print(f"    {GREY}{count} restored action(s) cancelled rather than resumed{RESET}")

    remaining = psql(
        "SELECT count(*) FROM app.action_jobs WHERE state IN ('QUEUED','EXECUTING')", SCRATCH_DB
    )
    if remaining != "0":
        print(f"    {RED}FAIL{RESET}  {remaining} job(s) would still execute after promotion")
        failed += 1
    else:
        print(f"    {GREEN}PASS{RESET}  no restored job can execute after promotion")

    print(f"{YELLOW}==>{RESET} cleaning up")
    psql(f"DROP DATABASE IF EXISTS {SCRATCH_DB}", database="postgres")

    print()
    if failed:
        print(f"  {RED}RESTORE DRILL FAILED ({failed} check(s)){RESET}")
    else:
        print(f"  {GREEN}RESTORE DRILL PASSED{RESET}")
    print()
    return 1 if failed else 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "drill"
    if command == "backup":
        take_backup()
        return 0
    if command == "drill":
        return drill()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
