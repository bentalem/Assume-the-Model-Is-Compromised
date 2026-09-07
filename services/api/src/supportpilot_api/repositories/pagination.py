"""Cursor pagination.

Every list and search tool is paginated and capped (SP-DATA-001 §8). This is not ergonomics — it is
what stops a single tool call from becoming a bulk export (`TS7-09`).

Cursors are keyset, not offset: an offset walk over a tenant-filtered set gets slower and, worse,
skips or repeats rows when the set changes underneath it. The cursor carries the sort key of the
last row returned, and is opaque so callers cannot craft one to reach past their tenant — a forged
cursor still runs under the same row policy, so at worst it returns nothing.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

DEFAULT_LIMIT = 20
MAX_LIMIT = 50


@dataclass(frozen=True)
class Page:
    rows: list[dict[str, Any]]
    next_cursor: str | None


def clamp_limit(requested: int | None, policy_max: int | None = None) -> int:
    """Resolve the page size actually used.

    The lowest of the requested value, the endpoint maximum, and any policy obligation wins. A
    policy that says max_results=5 cannot be widened by asking for 50.
    """
    limit = DEFAULT_LIMIT if requested is None else requested
    limit = max(1, min(limit, MAX_LIMIT))
    if policy_max is not None:
        limit = min(limit, policy_max)
    return limit


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    """Decode a cursor, or return None.

    A malformed cursor is treated as "start from the beginning" rather than an error. It carries no
    authority: the query it feeds runs under the caller's tenant context regardless of what the
    cursor claims.
    """
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def build_page(rows: list[dict[str, Any]], limit: int, cursor_fields: tuple[str, ...]) -> Page:
    """Trim an over-fetched result set into a page plus a next cursor.

    Callers fetch `limit + 1` rows. The extra row is the signal that more exist; it is never
    returned.
    """
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last = visible[-1]
        next_cursor = encode_cursor({field: str(last[field]) for field in cursor_fields})
    return Page(rows=visible, next_cursor=next_cursor)
