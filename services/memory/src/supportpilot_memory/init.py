"""memory-init: the one-shot job that prepares memory-db (and, from phase 2, Qdrant).

The equivalent of the core `migrate` job, and held to the same rules:

  * It is the only component that holds memory-db's bootstrap credential. Runtime services never
    receive it.
  * Roles are created here, with passwords read from mounted secret files and passed to PostgreSQL
    as quoted literals. They never appear in a committed file — which is why role creation lives in
    this module rather than in a migration.
  * Migrations are applied in order, each atomically, and recorded; the job fails if the number of
    files and the number recorded ever disagree, rather than starting a service on a database that
    was silently half-migrated.
  * The smoke tests run on every start, and a failure fails the job — which stops the memory
    service, since it depends on this job completing.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql

from .config import read_secret_file

ROOT = Path(os.environ.get("MEMORY_SQL_DIR", "/app/database/memory"))
VERSION = re.compile(r"^\d{4}_[a-z0-9_]+$")

# name -> (secret env var, LOGIN?)
ROLES = {
    "mem_migrator": ("MEMORY_MIGRATOR_SECRET_FILE", True),
    "mem_service_role": ("MEMORY_SERVICE_SECRET_FILE", True),
    "mem_range_role": ("MEMORY_RANGE_SECRET_FILE", True),
}


def log(message: str) -> None:
    print(f"[memory-init] {message}", flush=True)


def _notice(diag: psycopg.errors.Diagnostic) -> None:
    if diag.message_primary:
        log(diag.message_primary)


def connect() -> psycopg.Connection:
    params = dict(
        host=os.environ["MEMORY_DB_HOST"],
        port=int(os.environ.get("MEMORY_DB_PORT", "5432")),
        dbname=os.environ["MEMORY_DB_NAME"],
        user=os.environ["MEMORY_DB_BOOTSTRAP_USER"],
        password=read_secret_file("MEMORY_DB_BOOTSTRAP_SECRET_FILE"),
        application_name="memory-init",
    )
    for attempt in range(60):
        try:
            conn = psycopg.connect(**params, autocommit=True)
            conn.add_notice_handler(_notice)
            return conn
        except psycopg.OperationalError:
            if attempt == 59:
                raise
            time.sleep(1)
    raise SystemExit("unreachable")


def create_roles(conn: psycopg.Connection) -> None:
    for role, (secret_env, login) in ROLES.items():
        password = read_secret_file(secret_env)
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        if not exists:
            conn.execute(
                sql.SQL("CREATE ROLE {} {} PASSWORD {}").format(
                    sql.Identifier(role),
                    sql.SQL("LOGIN" if login else "NOLOGIN"),
                    sql.Literal(password),
                )
            )
            log(f"created role {role}")
        # Belt and braces, as the core does: whatever the role was created with, force the safe
        # attributes on every start.
        conn.execute(
            sql.SQL(
                "ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(role))
        )


def create_schemas(conn: psycopg.Connection) -> None:
    # Created by the bootstrap superuser and handed to the migration role, exactly as the core does:
    # the migration role holds no CREATE on the database, which is what stops its credential from
    # becoming a general-purpose one.
    conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    for schema in ("mem", "range_mem"):
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION mem_migrator").format(
                sql.Identifier(schema)
            )
        )
        conn.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema)))
    conn.execute("GRANT USAGE ON SCHEMA mem TO mem_service_role")
    conn.execute("GRANT USAGE ON SCHEMA range_mem TO mem_range_role")
    conn.execute("GRANT mem_migrator TO CURRENT_USER")
    conn.execute(
        "SET ROLE mem_migrator; "
        "CREATE TABLE IF NOT EXISTS mem.schema_migrations "
        "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()); "
        "RESET ROLE"
    )


def apply_migrations(conn: psycopg.Connection) -> int:
    files = sorted((ROOT / "migrations").glob("*.sql"))
    applied = 0
    for path in files:
        version = path.stem
        if not VERSION.match(version):
            raise SystemExit(f"migration file name is not a version: {path.name}")
        done = conn.execute(
            "SELECT 1 FROM mem.schema_migrations WHERE version = %s", (version,)
        ).fetchone()
        if done:
            log(f"skip {version} (already applied)")
            continue
        log(f"applying {version}")
        body = path.read_text(encoding="utf-8")
        # One transaction per file, including the row that records it. `version` has been checked
        # against a strict pattern above, so writing it into the statement cannot inject anything.
        conn.execute(
            "BEGIN;\n" + body + "\n;RESET ROLE;\n"
            f"INSERT INTO mem.schema_migrations (version) VALUES ('{version}');\nCOMMIT;"
        )
        applied += 1

    recorded = conn.execute("SELECT count(*) AS n FROM mem.schema_migrations").fetchone()[0]
    if recorded != len(files):
        raise SystemExit(f"FATAL: {len(files)} migration file(s) present but {recorded} recorded")
    log(f"applied {applied} migration(s); {recorded} of {len(files)} recorded")
    return applied


def apply_seeds(conn: psycopg.Connection) -> None:
    if os.environ.get("SEED_LOCAL_DATA", "false") != "true":
        return
    for path in sorted((ROOT / "seeds").glob("*.sql")):
        log(f"seeding {path.name}")
        conn.execute("BEGIN;\n" + path.read_text(encoding="utf-8") + "\n;COMMIT;")


def complete_forgets(conn: psycopg.Connection) -> None:
    """Finish every forget that was left half done — only while forgetting is set to be complete.

    The database half of 9.8's recovery; `qdrant_setup._remove_forgotten` is the vector half. While
    `forget.scope` is `primary`, a forgotten memory's summaries stay live, and that is the state the
    learner is there to find, so nothing is touched. Once it is back at `all`, whatever survived a
    forget is forgotten now, with an audit event each — so restoring the setting and re-running this
    job leaves the store as a complete forget would have, rather than a correct setting sitting on
    top of the copies it failed to remove.
    """
    scope = conn.execute("SELECT value FROM mem.settings WHERE key = 'forget.scope'").fetchone()
    if not scope or scope[0] != "all":
        log(f"forget.scope is {scope[0] if scope else None!r}; leaving surviving derivations in place")
        return
    with conn.transaction():
        rows = conn.execute(
            """
            WITH RECURSIVE survivors AS (
              SELECT r.id FROM mem.records r JOIN mem.records p ON r.derived_from = p.id
              WHERE p.deleted_at IS NOT NULL AND r.deleted_at IS NULL
              UNION
              SELECT r.id FROM mem.records r JOIN survivors s ON r.derived_from = s.id
              WHERE r.deleted_at IS NULL
            )
            UPDATE mem.records SET deleted_at = now()
            WHERE id IN (SELECT id FROM survivors)
            RETURNING id, org_id
            """
        ).fetchall()
        for record_id, org_id in rows:
            conn.execute(
                "INSERT INTO mem.audit_events (request_id, actor_type, actor_sub, org_id, action, "
                "resource_type, resource_id, decision, reason) VALUES ('memory-init', 'runtime', "
                "'memory-init', %s, 'memory.forget', 'memory', %s, 'succeeded', "
                "'completed:derived_from_forgotten')",
                (org_id, str(record_id)),
            )
    if rows:
        log(f"completed {len(rows)} forget(s) left half done")


def smoke_test(conn: psycopg.Connection) -> None:
    log("running permission and row-security smoke tests")
    conn.execute((ROOT / "tests" / "permissions_smoke.sql").read_text(encoding="utf-8"))


def main() -> int:
    conn = connect()
    try:
        create_roles(conn)
        create_schemas(conn)
        apply_migrations(conn)
        apply_seeds(conn)
        complete_forgets(conn)
        smoke_test(conn)
        version = conn.execute("SELECT max(version) FROM mem.schema_migrations").fetchone()[0]
        log(f"schema version: {version}")
    finally:
        conn.close()

    # Phase 2: Qdrant collections, indexes and seed vectors.
    try:
        from .qdrant_setup import setup as qdrant_setup
    except ModuleNotFoundError:
        qdrant_setup = None
    if qdrant_setup is not None:
        qdrant_setup(log)

    log("done")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
