"""Secrets are refused at write, because a secret in memory is a secret in a future context.

Everything written into the memory layer is replayed into some model's context later — history on
the next turn, long-term memory in the next conversation. So a credential that reaches a tool
result, and from there a stored turn or a memory, is not a one-off exposure. It is a standing one,
delivered to every future context that retrieves it. Challenge 9.1 arms the filter off.

Two write paths, two behaviours, one setting:

  * A **history turn** is redacted. The conversation has to be recorded — a runtime that could not
    store a tool result would break — but it is recorded without the secret.
  * A **long-term memory** is refused outright. A memory whose content is a credential has no
    legitimate reason to exist, and storing a redacted stub of one would be storing noise.

Detection reuses the patterns the log redactor already trusts (`observability._REDACTIONS`), so there
is one definition of "secret-shaped" in this service rather than two that drift. Pattern matching is
a floor, not a guarantee, and Stage 03 of 9.1 says so: it catches the credentials that look like
credentials. The real control is that the agent has nothing worth leaking and nowhere to send it.
"""

from __future__ import annotations

from typing import Any

import psycopg

from .observability import _REDACTIONS

REDACTED = "[secret withheld at write]"


def filter_enabled(cur: psycopg.Cursor[dict[str, Any]]) -> bool:
    """Whether the filter is on, read per request. Anything but an explicit 'off' counts as on.

    Deny by default: an unreadable or missing setting must not be the thing that lets a secret in.
    """
    cur.execute("SELECT mem.setting('write.secret_filter') AS value")
    row = cur.fetchone()
    return not (row and row["value"] == "off")


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern, _ in _REDACTIONS)


def redact(text: str) -> str:
    for pattern, _ in _REDACTIONS:
        text = pattern.sub(REDACTED, text)
    return text
