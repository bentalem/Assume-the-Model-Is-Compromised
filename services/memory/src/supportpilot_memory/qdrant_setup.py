"""Qdrant, as memory-init prepares it — and the reconciliation check that proves it agrees with memory-db.

memory-init is the only holder of Qdrant's API key. It uses it for three things here, all of them
things no runtime component may do: create collections, create payload indexes, and read every
tenant's records to write the vectors that are missing.

What it deliberately does not do is delete. A vector without a live record is reported by the
reconciliation check, not removed on startup — because challenge 9.8 arms a state in which exactly
those vectors exist, and a job that "repaired" it on every restart would erase the lesson and hide
the bug it describes. Repair is a separate, explicit act.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable

import httpx
import psycopg
from psycopg.rows import dict_row

from .config import read_secret_file
from .vectors import SHARED, parse_tenants

DIMENSIONS = 384  # BAAI/bge-small-en-v1.5


def _client() -> tuple[httpx.Client, str]:
    key = read_secret_file("QDRANT_ADMIN_KEY_FILE")
    return httpx.Client(timeout=30, headers={"api-key": key}), os.environ["QDRANT_URL"].rstrip("/")


def _collections(tenants: dict[str, str]) -> dict[str, str]:
    """collection name -> the layout it belongs to."""
    names = {f"memories__{slug}": "per_tenant" for slug in tenants.values()}
    names[SHARED] = "shared"
    return names


def _records(conn: psycopg.Connection) -> list[dict[str, Any]]:
    # As the bootstrap superuser: the one view of every tenant's records, which only this job has.
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id::text AS id, org_id::text AS org_id, owner_sub, content, content_hash, "
            "channel, status, deleted_at IS NOT NULL AS deleted FROM mem.records"
        )
        return cur.fetchall()


def _points(client: httpx.Client, url: str, collection: str) -> dict[str, dict]:
    points: dict[str, dict] = {}
    offset = None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        response = client.post(f"{url}/collections/{collection}/points/scroll", json=body)
        response.raise_for_status()
        result = response.json()["result"]
        for point in result["points"]:
            points[str(point["id"])] = point.get("payload") or {}
        offset = result.get("next_page_offset")
        if offset is None:
            return points


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["MEMORY_DB_HOST"], dbname=os.environ["MEMORY_DB_NAME"],
        user=os.environ["MEMORY_DB_BOOTSTRAP_USER"],
        password=read_secret_file("MEMORY_DB_BOOTSTRAP_SECRET_FILE"), autocommit=True,
    )


def setup(log: Callable[[str], None]) -> None:
    tenants = parse_tenants(os.environ.get("MEMORY_TENANTS", ""))
    if not tenants:
        log("MEMORY_TENANTS is empty; skipping Qdrant setup")
        return
    client, url = _client()
    embedder = httpx.Client(timeout=60)
    embeddings = os.environ["EMBEDDINGS_URL"].rstrip("/")

    for collection, layout in _collections(tenants).items():
        exists = client.get(f"{url}/collections/{collection}").status_code == 200
        if not exists:
            client.put(f"{url}/collections/{collection}",
                       json={"vectors": {"size": DIMENSIONS, "distance": "Cosine"}}).raise_for_status()
            log(f"created collection {collection}")
        # The tenant field is indexed with is_tenant, as Qdrant's multitenancy guidance says. In the
        # shared layout that field is the organisation, and the index is an optimisation — it
        # makes the filter fast. It does not make the filter mandatory: nothing in Qdrant refuses a
        # query that leaves it out. That gap is challenge 9.6.
        tenant_field = "org_id" if layout == "shared" else "owner_sub"
        fields = {tenant_field: True, "status": False}
        if layout == "shared":
            fields["owner_sub"] = False
        for field, is_tenant in fields.items():
            schema: dict[str, Any] = {"type": "keyword"}
            if is_tenant:
                schema["is_tenant"] = True
            client.put(f"{url}/collections/{collection}/index?wait=true",
                       json={"field_name": field, "field_schema": schema}).raise_for_status()

    # Every live record gets a point in both layouts if it lacks one — seeds, and anything written
    # while Qdrant or the embedding model was unavailable. Missing only: nothing is overwritten or
    # deleted here.
    with _connect() as conn:
        records = [r for r in _records(conn) if not r["deleted"]]
    written = 0
    for collection, layout in _collections(tenants).items():
        existing = _points(client, url, collection)
        for record in records:
            slug = tenants.get(record["org_id"])
            belongs = layout == "shared" or collection == f"memories__{slug}"
            if not belongs or record["id"] in existing:
                continue
            response = embedder.post(f"{embeddings}/embed", json={"inputs": [record["content"]]})
            response.raise_for_status()
            payload = {
                "record_id": record["id"], "owner_sub": record["owner_sub"],
                "channel": record["channel"], "status": record["status"],
                "content_hash": record["content_hash"], "content": record["content"],
            }
            if layout == "shared":
                payload["org_id"] = record["org_id"]
            client.put(f"{url}/collections/{collection}/points?wait=true", json={"points": [
                {"id": record["id"], "vector": response.json()[0], "payload": payload}
            ]}).raise_for_status()
            written += 1
    removed = _remove_forgotten(client, url, tenants, log)
    log(f"qdrant ready: {len(_collections(tenants))} collection(s), {written} point(s) written, "
        f"{removed} stale point(s) removed")


def _forget_scope() -> str | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT value FROM mem.settings WHERE key = 'forget.scope'")
        row = cur.fetchone()
        return row[0] if row else None


def _remove_forgotten(client: httpx.Client, url: str, tenants: dict[str, str],
                      log: Callable[[str], None]) -> int:
    """Remove vectors whose record is forgotten or gone — only while forgetting is set to be complete.

    This is the repair half of challenge 9.8. While `forget.scope` is `primary` — armed — the stale
    vectors are the consequence the learner is there to find, so they are left exactly where they
    are and the reconciliation check keeps naming them. Once the setting is back at `all`, re-running
    this job brings the store back to the state `forget` would have left: which is how the Range's
    restore for 9.8 has a proven inverse, rather than a restored setting sitting on top of the debris
    it caused.
    """
    scope = _forget_scope()
    if scope != "all":
        log(f"forget.scope is {scope!r}; leaving stale points for the reconciliation check to name")
        return 0
    with _connect() as conn:
        live = {r["id"] for r in _records(conn) if not r["deleted"]}
    removed = 0
    for collection in _collections(tenants):
        stale = [pid for pid in _points(client, url, collection) if pid not in live]
        if stale:
            client.post(f"{url}/collections/{collection}/points/delete?wait=true",
                        json={"points": stale}).raise_for_status()
            removed += len(stale)
            log(f"{collection}: removed {len(stale)} point(s) for records that are not live")
    return removed


def reconcile() -> int:
    """Report every disagreement between memory-db and Qdrant, naming the record and the layout.

    Clean means: every live record has a point in its tenant's collection and in the shared one,
    with the same content hash, and no collection holds a point for a record that is not live.
    Exit status 0 when clean, 1 otherwise. Reports; never repairs.
    """
    tenants = parse_tenants(os.environ.get("MEMORY_TENANTS", ""))
    client, url = _client()
    with _connect() as conn:
        records = {r["id"]: r for r in _records(conn)}
    problems: list[str] = []
    for collection, layout in _collections(tenants).items():
        points = _points(client, url, collection)
        for rid, record in records.items():
            slug = tenants.get(record["org_id"])
            belongs = layout == "shared" or collection == f"memories__{slug}"
            if not belongs:
                continue
            if record["deleted"]:
                if rid in points:
                    problems.append(f"{collection}: holds a point for forgotten record {rid}")
            elif rid not in points:
                problems.append(f"{collection}: no point for live record {rid}")
            elif points[rid].get("content_hash") != record["content_hash"]:
                problems.append(f"{collection}: content hash differs for record {rid}")
        for pid in points:
            if pid not in records:
                problems.append(f"{collection}: point {pid} has no record at all")
    for line in problems:
        print(f"[reconcile] {line}")
    print(f"[reconcile] {'clean' if not problems else f'{len(problems)} disagreement(s)'}: "
          f"{len(records)} record(s) across {len(_collections(tenants))} collection(s)")
    return 1 if problems else 0


def reconcile_main() -> int:  # pragma: no cover - console entry point
    return reconcile()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(reconcile())
