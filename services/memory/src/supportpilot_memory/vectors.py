"""The vector store (Qdrant) and the embedding model — retrieval by meaning.

Qdrant is a second copy of every memory, kept so that "memories relevant to this question" can be
found. It is never the source of truth: memory-db is. Two consequences run through this module:

  * Everything read from Qdrant is a *candidate*. Recall and context assembly take the ids Qdrant
    ranked and read the records back from memory-db, under row-level security. A record Qdrant
    returns that the caller may not see is dropped there, whatever Qdrant thought.
  * Everything written to Qdrant happens after the memory-db transaction commits, from the outbox.
    Qdrant is not transactional, so the two cannot be written in one step; the outbox and the
    reconciliation check are how they are kept honest.

Two layouts exist, and the service writes both on every change:

  * **Per-tenant** (the default): one collection per organisation, reached only with that
    organisation's token. A query built wrongly can at worst see its own tenant's memories —
    the credential cannot open the other tenant's collection. Measured: a cedar token gets 403 on
    northwind's collection.
  * **Shared**: one collection for everyone, partitioned by an `org_id` payload field. This is
    Qdrant's own recommended layout at scale, and in it the only thing separating tenants is the
    filter this service adds to each query. Challenge 9.6 arms it.

Dual-writing both layouts is a lab artifact, stated plainly: it is what lets 9.6 arm and restore in
one step with nothing to re-index. A real per-tenant deployment would hold no shared credential at
all, and this service does only because both layouts must stay populated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .errors import ApiError, unavailable

logger = logging.getLogger(__name__)

SHARED = "memories__shared"
LAYOUTS = ("per_tenant", "shared")


def no_store_for_tenant() -> ApiError:
    """An organisation this deployment has no collection for. Refused, never defaulted to shared."""
    return ApiError(503, "unavailable")


@dataclass(frozen=True)
class Candidate:
    record_id: str
    score: float


class VectorStore:
    def __init__(self, url: str, token_dir: str, tenants: dict[str, str], timeout: float = 10.0):
        self._url = url.rstrip("/")
        self._tenants = dict(tenants)  # org_id -> slug
        directory = Path(token_dir)
        self._tokens = {
            slug: (directory / f"qdrant_jwt_{slug}").read_text(encoding="utf-8").strip()
            for slug in self._tenants.values()
        }
        self._shared_token = (directory / "qdrant_jwt_shared").read_text(encoding="utf-8").strip()
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    # --------------------------------------------------------------------------------------------
    def _target(self, org_id: str, layout: str) -> tuple[str, str]:
        """The collection and the credential for one organisation in one layout."""
        if layout == "shared":
            return SHARED, self._shared_token
        slug = self._tenants.get(org_id)
        if slug is None:
            # No collection and no credential for this organisation. Falling back to the shared
            # collection here would be exactly "memory without the tenant boundary"; refuse instead.
            raise no_store_for_tenant()
        return f"memories__{slug}", self._tokens[slug]

    def _call(self, method: str, path: str, token: str, payload: dict | None = None) -> dict:
        try:
            response = self._client.request(
                method, f"{self._url}{path}", json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError:
            logger.error("vector_store_unreachable", exc_info=True)
            raise unavailable() from None
        if response.status_code >= 400:
            logger.error("vector_store_error", extra={"status": response.status_code, "path": path})
            raise unavailable()
        return response.json() if response.content else {}

    # --------------------------------------------------------------------------------------------
    def upsert(self, *, org_id: str, record_id: str, vector: list[float],
               payload: dict[str, Any]) -> None:
        """Write one point to both layouts. The shared copy also carries the organisation."""
        for layout in LAYOUTS:
            collection, token = self._target(org_id, layout)
            point_payload = dict(payload, org_id=org_id) if layout == "shared" else dict(payload)
            self._call("PUT", f"/collections/{collection}/points?wait=true", token,
                       {"points": [{"id": record_id, "vector": vector, "payload": point_payload}]})

    def delete(self, *, org_id: str, record_ids: list[str]) -> None:
        if not record_ids:
            return
        for layout in LAYOUTS:
            collection, token = self._target(org_id, layout)
            self._call("POST", f"/collections/{collection}/points/delete?wait=true", token,
                       {"points": record_ids})

    def search(self, *, org_id: str, owner_sub: str, layout: str, vector: list[float],
               limit: int) -> list[Candidate]:
        """Candidates for one caller: their own confirmed memories, ranked by meaning.

        The filter below is the application's own. In the per-tenant layout it narrows within a
        collection the credential already confines to one organisation. In the shared layout it is
        the only thing that keeps one organisation's memories out of another's results — which is
        the whole of challenge 9.6.

        Ranking is by score, then by record id, so equal scores always come back in one order. No
        flag, check or observation depends on a score.
        """
        collection, token = self._target(org_id, layout)
        must = [
            {"key": "owner_sub", "match": {"value": owner_sub}},
            {"key": "status", "match": {"value": "confirmed"}},
        ]
        if layout == "shared":
            must.insert(0, {"key": "org_id", "match": {"value": org_id}})
        body = self._call("POST", f"/collections/{collection}/points/search", token, {
            "vector": vector, "limit": limit, "with_payload": False, "filter": {"must": must},
        })
        hits = [Candidate(record_id=str(hit["id"]), score=float(hit["score"]))
                for hit in body.get("result", [])]
        return sorted(hits, key=lambda h: (-h.score, h.record_id))

    def healthy(self) -> bool:
        try:
            return self._client.get(f"{self._url}/healthz", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False


class Embedder:
    """The local embedding model. No external API, no key, no egress."""

    def __init__(self, url: str, timeout: float = 15.0) -> None:
        self._url = url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.post(f"{self._url}/embed", json={"inputs": [text]})
            response.raise_for_status()
            return response.json()[0]
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            logger.error("embeddings_unavailable", exc_info=True)
            raise unavailable() from None

    def healthy(self) -> bool:
        try:
            return self._client.get(f"{self._url}/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False


def parse_tenants(value: str) -> dict[str, str]:
    """`org_id:slug,org_id:slug` — the organisations this deployment has a collection for.

    A new organisation is a new entry here, a new collection and a newly minted token. That is the
    honest operational cost of the per-tenant layout, and the usual reason teams choose the shared
    one instead — challenge 9.6's Stage 03 is about what that trade actually buys.
    """
    tenants: dict[str, str] = {}
    for pair in filter(None, (p.strip() for p in value.split(","))):
        org_id, _, slug = pair.partition(":")
        if not org_id or not slug:
            raise ValueError(f"malformed tenant entry: {pair!r}")
        tenants[org_id.strip()] = slug.strip()
    return tenants
