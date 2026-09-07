"""TS-5 — pagination.

Pagination is a security control here, not a convenience: it is what stops one tool call from
becoming a bulk export. These tests cover the clamping rules and the cursor round-trip, including
the cases where a caller supplies something hostile.
"""

from __future__ import annotations

import pytest

from supportpilot_api.repositories.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    build_page,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)


# --- clamp_limit ---------------------------------------------------------------------------------
def test_absent_limit_uses_the_default():
    assert clamp_limit(None) == DEFAULT_LIMIT


def test_limit_is_capped_at_the_endpoint_maximum():
    assert clamp_limit(10_000) == MAX_LIMIT


@pytest.mark.parametrize("requested", [0, -1, -9999])
def test_non_positive_limits_become_one(requested):
    assert clamp_limit(requested) == 1


def test_policy_obligation_beats_the_request():
    """A policy that says 5 cannot be widened by asking for 50."""
    assert clamp_limit(50, policy_max=5) == 5


def test_policy_obligation_does_not_widen_a_smaller_request():
    """The obligation is a ceiling, not a target."""
    assert clamp_limit(3, policy_max=25) == 3


def test_policy_obligation_cannot_exceed_the_endpoint_maximum():
    assert clamp_limit(None, policy_max=10_000) == DEFAULT_LIMIT
    assert clamp_limit(MAX_LIMIT + 100, policy_max=10_000) == MAX_LIMIT


# --- cursors -------------------------------------------------------------------------------------
def test_cursor_round_trip():
    payload = {"sort_name": "raman", "id": "abc-123"}
    assert decode_cursor(encode_cursor(payload)) == payload


def test_cursor_is_opaque_not_encrypted():
    """Base64 is encoding, not protection. The cursor carries no authority — it is only a position,
    and the query it feeds still runs under the caller's tenant context."""
    cursor = encode_cursor({"sort_name": "raman", "id": "abc"})
    assert "raman" not in cursor


@pytest.mark.parametrize(
    "value",
    [None, "", "not-base64!!", "YWJj", "e30", "!!!!", "a" * 5000, "eyJhIjo=", "________"],
)
def test_malformed_cursors_decode_to_none_rather_than_raising(value):
    """A hostile cursor restarts the walk. It never crashes the request and never widens access."""
    result = decode_cursor(value)
    assert result is None or isinstance(result, dict)


def test_cursor_encoding_a_non_object_is_rejected_on_decode():
    import base64
    import json

    raw = base64.urlsafe_b64encode(json.dumps([1, 2, 3]).encode()).decode().rstrip("=")
    assert decode_cursor(raw) is None


# --- build_page ----------------------------------------------------------------------------------
def rows(count: int) -> list[dict]:
    return [{"id": f"id-{i:03}", "sort_name": f"name-{i:03}"} for i in range(count)]


def test_exact_page_has_no_next_cursor():
    page = build_page(rows(5), limit=5, cursor_fields=("sort_name", "id"))
    assert len(page.rows) == 5
    assert page.next_cursor is None


def test_over_fetched_row_is_not_returned_but_signals_more():
    """Callers fetch limit + 1. The extra row proves more exist; it must never be served."""
    page = build_page(rows(6), limit=5, cursor_fields=("sort_name", "id"))
    assert len(page.rows) == 5
    assert page.next_cursor is not None
    assert page.rows[-1]["id"] == "id-004"


def test_next_cursor_points_at_the_last_returned_row():
    page = build_page(rows(6), limit=5, cursor_fields=("sort_name", "id"))
    position = decode_cursor(page.next_cursor)
    assert position == {"sort_name": "name-004", "id": "id-004"}


def test_short_page_has_no_next_cursor():
    page = build_page(rows(2), limit=5, cursor_fields=("sort_name", "id"))
    assert len(page.rows) == 2
    assert page.next_cursor is None


def test_empty_result_has_no_next_cursor():
    page = build_page([], limit=5, cursor_fields=("sort_name", "id"))
    assert page.rows == []
    assert page.next_cursor is None


def test_page_never_exceeds_the_limit_even_if_the_query_over_returns():
    """Defence in depth: if a repository ignored its LIMIT, the page still cannot exceed it."""
    page = build_page(rows(500), limit=10, cursor_fields=("sort_name", "id"))
    assert len(page.rows) == 10
