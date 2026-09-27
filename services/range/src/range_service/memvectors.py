"""The Range's read-only view of the vector store (track 9).

Two challenges ask where content lives in Qdrant: 9.6 (what a credential can reach when the filter is
left out) and 9.8 (whether a forgotten memory's points are still there). The database cannot answer
either — it cannot see into Qdrant — so the Range asks Qdrant itself.

It does so with read-only tokens, one per collection, minted by bootstrap and mounted here. A token
grants `r` on one collection: it can scroll and retrieve, it cannot write, and it cannot touch a
collection it does not name — the Range has no way to change the store, only to look at it. That is a
grant, and compose names it as one.

Collection names and token names are literals from registry.py. Nothing from a request reaches a URL
built here.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("supportpilot.range.memvectors")

QDRANT = os.environ.get("QDRANT_URL", "http://qdrant:6333")
TOKEN_DIR = Path(os.environ.get("RANGE_QDRANT_TOKEN_DIR", "/run/secrets"))

# collection -> the read-only token that names it
TOKENS = {
    "memories__cedar": "range_qdrant_cedar_ro",
    "memories__northwind": "range_qdrant_northwind_ro",
    "memories__shared": "range_qdrant_shared_ro",
}


def _request(method: str, path: str, token_name: str, body: dict | None = None) -> tuple[int, Any]:
    token = (TOKEN_DIR / token_name).read_text(encoding="utf-8").strip()
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{QDRANT}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:  # noqa: BLE001 — reported as a row, never guessed at
        logger.warning("qdrant unreachable: %s", type(exc).__name__)
        return 0, None


def scroll_unfiltered(collection: str, token_name: str, limit: int = 20) -> tuple[int, list[dict]]:
    """Every point the token can see in a collection, with no filter at all — capped."""
    status, body = _request("POST", f"/collections/{collection}/points/scroll", token_name,
                            {"limit": limit, "with_payload": True, "with_vector": False})
    points = (body or {}).get("result", {}).get("points", []) if status == 200 else []
    return status, points


def point_present(collection: str, point_id: str) -> tuple[int, dict | None]:
    """Is there a point for this record id? (status, payload)."""
    status, body = _request("GET", f"/collections/{collection}/points/{point_id}",
                            TOKENS[collection])
    if status == 200 and body and body.get("result"):
        return 200, body["result"].get("payload") or {}
    return status, None
