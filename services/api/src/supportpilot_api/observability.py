"""Structured logging, redaction, and metrics.

Logs are JSON so they can be searched and correlated across services (SP-OPS-001 §7). Every line
carries the request id, which is what makes "reconstruct one request across Onyx, API, OPA, database
and worker" possible.

The redaction filter is the part that matters for security. It is not a formatting nicety: the
baseline requires that no secret reaches a log, and a filter on the logging pipeline catches the
cases a code review will not — an exception message that happens to contain a DSN, a third-party
library logging a request header, a debugging line someone left in.

It redacts by *pattern*, not by field name, because the field name is exactly what you cannot rely
on when the leak is accidental.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import Counter
from typing import Any

#: Patterns whose *values* must never appear in a log line.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    # Connection strings, including the password= form psycopg builds.
    (re.compile(r"password=\S+"), "password=[redacted]"),
    (re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@"), "postgresql://[redacted]@"),
    # Bearer tokens and raw JWTs, wherever they turn up.
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [redacted]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]+"), "[redacted-jwt]"),
    # Provider-style API keys.
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "[redacted-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted-key]"),
    # Anything assigned to a credential-shaped name.
    (
        re.compile(
            # The optional quote after the name matters: in JSON the key is written "api_key":,
            # and without it the most common shape in our own logs would slip through.
            r"(?i)([a-z0-9_.-]*(?:password|passwd|secret|api[_-]?key|token|credential)"
            r"[a-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?([^\s\"',}]{6,})"
        ),
        r"\1=[redacted]",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Applies redaction to the formatted message and to every string argument.

    Installed on the root logger, so it covers libraries too — the leaks worth catching are the
    ones nobody wrote deliberately.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            else:
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        # Tracebacks are a common accidental carrier: a psycopg error can quote the DSN.
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with extras promoted to top-level fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["error"] = redact(self.formatException(record.exc_info))[:2000]
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers; route them through ours so access lines are redacted too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


# ------------------------------------------------------------------------------------------------
# Metrics
#
# The signals SP-OPS-001 §7 asks for, in Prometheus text format. Counters only, held in memory:
# this is a local build, and a metrics backend is part of the production platform decision (OD-04).
# ------------------------------------------------------------------------------------------------
class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self._started = time.time()

    def increment(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += 1

    def render(self) -> str:
        lines = [
            "# HELP supportpilot_uptime_seconds Seconds since this process started.",
            "# TYPE supportpilot_uptime_seconds gauge",
            f"supportpilot_uptime_seconds {time.time() - self._started:.0f}",
        ]
        with self._lock:
            counters = dict(self._counters)

        by_name: dict[str, list[tuple[tuple[tuple[str, str], ...], int]]] = {}
        for (name, labels), value in counters.items():
            by_name.setdefault(name, []).append((labels, value))

        for name in sorted(by_name):
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(by_name[name]):
                rendered = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"{name}{{{rendered}}} {value}" if rendered else f"{name} {value}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
