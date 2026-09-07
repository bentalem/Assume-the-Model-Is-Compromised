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
from psycopg.rows import dict_row

from .adapters.refund import FakeRefundAdapter
from .jobs.processor import JobProcessor, RefusedToExecute

logger = logging.getLogger("supportpilot.worker")


def _configure_logging(level: str) -> None:
    """JSON lines with redaction, matching the API.

    The worker handles the credential with the widest blast radius — the provider credential — so
    a redaction filter here is not optional. It is a copy rather than a shared package because the
    two services are deployed independently and must not couple through a library for four
    regexes; if a third service needs it, that is the moment to extract one.
    """
    import json as _json
    import re as _re

    patterns = [
        (_re.compile(r"password=\S+"), "password=[redacted]"),
        (_re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@"), "postgresql://[redacted]@"),
        (_re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [redacted]"),
        (_re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[redacted-key]"),
        (
            _re.compile(
                r"(?i)([a-z0-9_.-]*(?:password|secret|api[_-]?key|token|credential)[a-z0-9_.-]*)"
                r"[\"']?\s*[:=]\s*[\"']?([^\s\"',}]{6,})"
            ),
            r"=[redacted]",
        ),
    ]

    def _redact(text: str) -> str:
        for pattern, replacement in patterns:
            text = pattern.sub(replacement, text)
        return text

    reserved = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
        "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
    }

    class _Formatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "event": _redact(record.getMessage()),
                "service": "worker",
            }
            for key, value in record.__dict__.items():
                if key not in reserved and not key.startswith("_"):
                    payload[key] = value
            if record.exc_info:
                payload["error"] = _redact(self.formatException(record.exc_info))[:2000]
            return _json.dumps(payload, default=str)

    handler = logging.StreamHandler()
    handler.setFormatter(_Formatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

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
            SELECT (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls) AS privileged
            FROM pg_roles WHERE rolname = current_user
            """
        )
        row = cur.fetchone()
        if row and row["privileged"]:
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
    _configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    poll_interval = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))

    for attempt in range(30):
        try:
            conn = psycopg.connect(_dsn(), row_factory=dict_row)
            break
        except psycopg.OperationalError:
            logger.info("waiting_for_database", extra={"attempt": attempt})
            time.sleep(2)
    else:
        logger.error("database_unreachable")
        sys.exit(1)

    with conn:
        verify_least_privilege(conn)

        # OD-02 has not chosen a provider, so the fake adapter is what runs. It enforces the same
        # idempotency a real provider must, so retry bugs surface here rather than in a sandbox.
        adapter = FakeRefundAdapter()
        worker_id = f"worker-{os.getpid()}"
        lease_seconds = int(os.environ.get("WORKER_LEASE_SECONDS", "300"))
        processor = JobProcessor(conn, adapter, worker_id=worker_id, lease_seconds=lease_seconds)

        logger.info("worker_started", extra={"poll_interval": poll_interval, "id": worker_id})

        while _running:
            try:
                job = processor.claim()
            except Exception:
                logger.error("claim_failed", exc_info=True)
                conn.rollback()
                time.sleep(poll_interval)
                continue

            if job is None:
                time.sleep(poll_interval)
                continue

            try:
                key = processor.verify(job)
            except RefusedToExecute as refusal:
                # A failed check is never retried into success. The job is closed and the refusal
                # recorded with its reason.
                processor.refuse(job, refusal.reason)
                continue
            except Exception:
                logger.error("verification_error", exc_info=True)
                conn.rollback()
                processor.refuse(job, "verification_error")
                continue

            try:
                outcome = processor.execute(job, key)
                logger.info(
                    "job_finished",
                    extra={"job": job.job_id, "outcome": str(outcome)},
                )
            except Exception:
                logger.error("execution_error", exc_info=True)
                conn.rollback()
                processor.refuse(job, "execution_error")

    logger.info("worker_stopped")


if __name__ == "__main__":  # pragma: no cover
    run()
