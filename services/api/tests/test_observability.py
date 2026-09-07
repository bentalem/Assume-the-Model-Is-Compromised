"""Phase 5 — log redaction.

ST-05 says no secret reaches a log. A code review cannot enforce that, because the leaks that
matter are the ones nobody wrote on purpose: an exception whose message quotes a DSN, a library
logging an Authorization header, a debug line left behind. So the filter is tested against those
shapes rather than against tidy examples.
"""

from __future__ import annotations

import json
import logging

import pytest

from supportpilot_api.observability import JsonFormatter, RedactingFilter, redact


@pytest.mark.parametrize(
    ("text", "leaked"),
    [
        # A psycopg DSN, which appears verbatim in connection errors.
        (
            "connection failed: host=postgres dbname=supportpilot user=sp_api_role "
            "password=Xk9mP2vL8qR4wN7z application_name=supportpilot-api",
            "Xk9mP2vL8qR4wN7z",
        ),
        ("postgresql://sp_api_role:Xk9mP2vL8qR4wN7z@postgres:5432/supportpilot", "Xk9mP2vL8qR4wN7z"),
        ("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.sIgNaTuRe", "sIgNaTuRe"),
        ("token=eyJhbGciOiJIUzI1NiJ9.eyJhIjoxfQ.abcdefghijklmnop", "abcdefghijklmnop"),
        ("provider key sk-ant-abcdefghijklmnopqrstuvwxyz", "sk-ant-abcdefghijklmnopqrstuvwxyz"),
        ("aws key AKIAIOSFODNN7EXAMPLE rotated", "AKIAIOSFODNN7EXAMPLE"),
        ('{"api_key": "Zk3Qw9Lm2Pv6Tt77"}', "Zk3Qw9Lm2Pv6Tt77"),
        ("DB_PASSWORD=hunter2hunter2", "hunter2hunter2"),
        ("client_secret: s3cr3t-value-here", "s3cr3t-value-here"),
    ],
)
def test_secret_shapes_are_redacted(text, leaked):
    assert leaked not in redact(text)


def test_redaction_keeps_the_surrounding_context():
    """A redacted line must still be useful for debugging."""
    result = redact("connection failed: host=postgres password=Xk9mP2vL8qR4wN7z port=5432")
    assert "host=postgres" in result
    assert "port=5432" in result
    assert "[redacted]" in result


def test_ordinary_text_is_untouched():
    line = "order ORD-2001 read by alice in cedar; 6 fields returned"
    assert redact(line) == line


def test_the_word_password_alone_is_not_redacted():
    """Redaction targets values, not vocabulary. Over-redacting makes logs useless."""
    assert redact("the user was asked to reset their password") == (
        "the user was asked to reset their password"
    )


# --- the filter on a real log record --------------------------------------------------------------
def emit(message, *args, exc_info=None, **extra) -> dict:
    logger = logging.getLogger("test.redaction")
    record = logger.makeRecord(
        "test.redaction", logging.INFO, __file__, 1, message, args, exc_info, extra=extra or None
    )
    if exc_info:
        record.exc_text = logging.Formatter().formatException(exc_info)
    assert RedactingFilter().filter(record) is True
    return json.loads(JsonFormatter().format(record))


def test_filter_redacts_the_message():
    payload = emit("connect failed password=Xk9mP2vL8qR4wN7z")
    assert "Xk9mP2vL8qR4wN7z" not in json.dumps(payload)


def test_filter_redacts_string_arguments():
    payload = emit("dsn was %s", "password=Xk9mP2vL8qR4wN7z")
    assert "Xk9mP2vL8qR4wN7z" not in json.dumps(payload)


def test_filter_redacts_a_traceback():
    try:
        raise RuntimeError("could not connect with password=Xk9mP2vL8qR4wN7z")
    except RuntimeError:
        import sys

        payload = emit("database_error", exc_info=sys.exc_info())
    assert "Xk9mP2vL8qR4wN7z" not in json.dumps(payload)
    assert "error" in payload


# --- the JSON shape --------------------------------------------------------------------------------
def test_output_is_one_json_object_per_line():
    payload = emit("order_read", request_id="req-1", organization="cedar")
    assert payload["level"] == "INFO"
    assert payload["event"] == "order_read"
    assert payload["request_id"] == "req-1"
    assert payload["organization"] == "cedar"


def test_extras_are_promoted_so_a_request_can_be_correlated():
    """request_id must be a top-level field, not buried in the message."""
    payload = emit("policy_denied", request_id="req-42", reason="not_a_member")
    assert payload["request_id"] == "req-42"
    assert payload["reason"] == "not_a_member"


def test_formatter_never_raises_on_an_unserializable_extra():
    payload = emit("odd", thing=object())
    assert "thing" in payload
