"""SupportPilot worker.

Phase 4 gives this service its jobs. What exists now is the shape that phase 4 fills in, and — more
usefully at this stage — a running assertion that the worker's database role is as narrow as the
design says it is.

The worker deliberately has no route to OPA and no inbound port. It claims approved work and
executes allowlisted effects; it never makes an authorization decision and never accepts an
instruction from a model.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

import psycopg

logger = logging.getLogger("supportpilot.worker")

_running = True


def _stop(signum: int, _frame: object) -> None:
    global _running
    logger.info("shutdown_requested", extra={"signal": signum})
    _running = False


def _dsn() -> str:
    password_file = os.environ["WORKER_DATABASE_SECRET_FILE"]
    password = Path(password_file).read_text(encoding="utf-8").strip("\r\n")
    return (
        f"host={os.environ['DATABASE_HOST']} port={os.environ.get('DATABASE_PORT', '5432')} "
        f"dbname={os.environ['DATABASE_NAME']} user={os.environ['DATABASE_USER']} "
        f"password={password} application_name=supportpilot-worker"
    )


def verify_least_privilege(conn: psycopg.Connection) -> None:
    """Refuse to start if the worker role has more authority than the design allows.

    A worker that can read customer data is a finding, not a convenience. Failing at startup makes
    that impossible to miss (TS3-04). Phase 4 extends this to the action tables.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls
            FROM pg_roles WHERE rolname = current_user
            """
        )
        row = cur.fetchone()
        if row and row[0]:
            raise SystemExit("FATAL: worker role holds a privileged attribute")

        # The worker holds no grant on customer or order data. Probing must fail.
        for table in ("app.customers", "app.orders"):
            try:
                cur.execute(f"SELECT 1 FROM {table} LIMIT 1")  # noqa: S608 - fixed literal list
            except psycopg.errors.InsufficientPrivilege:
                conn.rollback()
                continue
            raise SystemExit(f"FATAL: worker role can read {table}; grants are too wide")

    logger.info("least_privilege_verified")


def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    poll_interval = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))

    for attempt in range(30):
        try:
            conn = psycopg.connect(_dsn())
            break
        except psycopg.OperationalError:
            logger.info("waiting_for_database", extra={"attempt": attempt})
            time.sleep(2)
    else:
        logger.error("database_unreachable")
        sys.exit(1)

    with conn:
        verify_least_privilege(conn)
        logger.info("worker_started", extra={"poll_interval": poll_interval})

        while _running:
            # Phase 4 (P4-12): claim one job with FOR UPDATE SKIP LOCKED, verify approval state,
            # expiry, payload hash and idempotency, then execute through an allowlisted adapter.
            # Until those tables exist there is nothing to claim.
            time.sleep(poll_interval)

    logger.info("worker_stopped")


if __name__ == "__main__":  # pragma: no cover
    run()
