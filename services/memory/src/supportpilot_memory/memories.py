"""Long-term memory: remember, recall, forget — and, for the runtime, confirm and summarise.

Three of these are model-facing and appear in the memory action document: `remember`, `recall` and
`forget`. `confirm` and `summaries` are for the agent runtime acting on the user's behalf and do not
appear there: a model that could confirm its own memories would make "unconfirmed" meaningless.

The rule the whole of track 9's write path rests on: **what the agent writes is unconfirmed**, and
unconfirmed memory never enters context. Something the agent merely *read* — a ticket, a web page,
a tool result — cannot make itself permanent just by persuading the agent to call `remember`. It
has to be confirmed by the user, through a route the model does not have. The store enforces this
too (0003's insert policy), not only this module.

Order of work in every write, and it matches the API's: validate → verify → resolve principal →
read settings → open transaction with context → write record + audit + outbox → commit → apply the
outbox to Qdrant → bounded response.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from . import audit
from .dependencies import Scope, request_scope
from .errors import ApiError, not_found
from .secrets_filter import contains_secret, filter_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["memory"])

MemoryId = Annotated[str, Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
RECALL_PAGE = 10
RECALL_CEILING = 30  # the most candidates one recall will ever consider, whatever the cursor says


def secret_refused() -> ApiError:
    """A memory whose content is a credential has no reason to exist. Refused, not redacted."""
    return ApiError(422, "secret_refused")


# ------------------------------------------------------------------------------------------------
# Schemas. Nothing here names a user, an organisation, a role, a channel, a status or an approval:
# all of those are decided by the server from the verified token and the endpoint that was called.
# ------------------------------------------------------------------------------------------------
class Remember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=2000,
                         description="The fact or preference to remember, in one or two sentences.")


class Remembered(BaseModel):
    memory_id: str
    # Whether it will be used. "unconfirmed" means stored, but kept out of every context until the
    # user confirms it — which the model cannot do.
    status: str


class Memory(BaseModel):
    memory_id: str
    content: str
    created_at: str


class RecallResult(BaseModel):
    results: list[Memory] = Field(max_length=RECALL_PAGE)
    next_cursor: str | None = Field(default=None,
                                    description="Opaque cursor for the next page, or null.")


class Forgotten(BaseModel):
    memory_id: str
    forgotten: bool


class Confirmed(BaseModel):
    memory_id: str
    status: str


class Summarised(BaseModel):
    memory_id: str
    derived_from: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _setting(cur, key: str) -> str | None:
    cur.execute("SELECT mem.setting(%s) AS value", (key,))
    row = cur.fetchone()
    return row["value"] if row else None


# ------------------------------------------------------------------------------------------------
# remember — model-facing
# ------------------------------------------------------------------------------------------------
@router.post("", status_code=201, response_model=Remembered, operation_id="remember",
             summary="Remember a fact or preference for the signed-in user")
def remember(body: Remember, scope: Scope = Depends(request_scope)) -> Remembered:
    principal = scope.principal
    services = scope.services
    refused = False
    record = None

    with services.db.transaction(principal) as cur:
        if filter_enabled(cur) and contains_secret(body.content):
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.remember", decision="denied", reason="secret_refused")
            refused = True
        else:
            # The channel is decided by which endpoint was called, never by the body: this is the
            # model's route, so this is the agent writing. Unconfirmed, unless the deployment has
            # chosen to auto-confirm — and the insert policy checks that same setting.
            auto = _setting(cur, "write.auto_confirm") == "true"
            status = "confirmed" if auto else "unconfirmed"
            cur.execute(
                "INSERT INTO mem.records (org_id, owner_sub, content, content_hash, channel, status, "
                "confirmed_at, confirmed_via) VALUES (%s, %s, %s, %s, 'agent', %s, "
                "CASE WHEN %s THEN now() END, CASE WHEN %s THEN 'auto' END) RETURNING id",
                (principal.org_id, principal.subject, body.content, _hash(body.content), status,
                 auto, auto),
            )
            record = {"id": str(cur.fetchone()["id"]), "content": body.content, "status": status,
                      "channel": "agent"}
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.remember", decision="succeeded",
                         reason="auto_confirmed" if auto else "stored_unconfirmed",
                         resource_type="memory", resource_id=record["id"])
            _enqueue(cur, principal.org_id, record["id"], "upsert")

    if refused:
        raise secret_refused()
    _apply_upserts(scope, [record])
    return Remembered(memory_id=record["id"], status=record["status"])


# ------------------------------------------------------------------------------------------------
# recall — model-facing
# ------------------------------------------------------------------------------------------------
@router.get("/search", response_model=RecallResult, operation_id="recall",
            summary="Recall the signed-in user's confirmed memories relevant to a question")
def recall(
    q: Annotated[str, Query(min_length=2, max_length=300,
                            description="What to look for, in plain words.")],
    cursor: Annotated[str | None, Query(pattern=r"^[0-9]{1,2}$",
                                        description="Opaque cursor from a previous page.")] = None,
    scope: Scope = Depends(request_scope),
) -> RecallResult:
    principal = scope.principal
    services = scope.services
    offset = int(cursor or 0)
    if offset >= RECALL_CEILING:
        return RecallResult(results=[], next_cursor=None)

    with services.db.transaction(principal) as cur:
        layout = "shared" if _setting(cur, "store.layout") == "shared" else "per_tenant"

    vector = services.extras["embedder"].embed(q)
    candidates = services.extras["vectors"].search(
        org_id=principal.org_id, owner_sub=principal.subject, layout=layout, vector=vector,
        limit=RECALL_CEILING,
    )
    window = candidates[offset:offset + RECALL_PAGE]

    with services.db.transaction(principal) as cur:
        # The candidates are read back from the source of truth, under row-level security. Anything
        # Qdrant returned that this caller may not see, or that has been forgotten, or that is not
        # confirmed, is dropped here — whatever the vector store believed.
        rows = []
        if window:
            cur.execute(
                "SELECT id, content, created_at FROM mem.records "
                "WHERE id = ANY(%s::uuid[]) AND status = 'confirmed'",
                ([c.record_id for c in window],),
            )
            rows = {str(r["id"]): r for r in cur.fetchall()}
        audit.record(cur, request_id=scope.request_id, principal=principal,
                     action="memory.recall", decision="allowed",
                     reason=f"returned_{len(rows)}_of_{len(window)}_candidates")

    results = [Memory(memory_id=c.record_id, content=rows[c.record_id]["content"],
                      created_at=rows[c.record_id]["created_at"].isoformat())
               for c in window if c.record_id in rows]
    more = offset + RECALL_PAGE < min(len(candidates), RECALL_CEILING)
    return RecallResult(results=results, next_cursor=str(offset + RECALL_PAGE) if more else None)


# ------------------------------------------------------------------------------------------------
# forget — model-facing
# ------------------------------------------------------------------------------------------------
@router.delete("/{memory_id}", response_model=Forgotten, operation_id="forget",
               summary="Forget one of the signed-in user's memories")
def forget(memory_id: MemoryId, scope: Scope = Depends(request_scope)) -> Forgotten:
    """Forgetting has to reach every copy, or it is only hiding.

    With `forget.scope` at its secure value this removes the record, everything derived from it
    (summaries of summaries included), and every one of their vectors in both layouts. Challenge
    9.8 arms `primary`, which removes the primary record only — gone from the list, and still in
    the vector store and in the summary made from it.
    """
    principal = scope.principal
    services = scope.services
    removed: list[str] = []
    found = False
    # Decided once, inside the transaction, and used after it. Reading the setting a second time
    # after commit would leave a window in which the record and its vectors disagreed about scope.
    delete_vectors = False

    with services.db.transaction(principal) as cur:
        cur.execute("SELECT id FROM mem.records WHERE id = %s", (memory_id,))
        found = cur.fetchone() is not None
        if not found:
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.forget", decision="denied", reason="not_visible",
                         resource_type="memory", resource_id=memory_id)
        else:
            everything = _setting(cur, "forget.scope") != "primary"
            if everything:
                cur.execute(
                    "WITH RECURSIVE tree AS ("
                    "  SELECT id FROM mem.records WHERE id = %s"
                    "  UNION"
                    "  SELECT r.id FROM mem.records r JOIN tree t ON r.derived_from = t.id"
                    ") SELECT id FROM tree",
                    (memory_id,),
                )
                removed = [str(r["id"]) for r in cur.fetchall()]
            else:
                removed = [memory_id]
            # Through the store's own function: a plain UPDATE of deleted_at is refused by row-level
            # security, because the forgotten row would no longer pass the read policy (0007).
            cur.execute("SELECT mem.forget_records(%s::uuid[]) AS changed", (removed,))
            if everything:
                for rid in removed:
                    _enqueue(cur, principal.org_id, rid, "delete")
            delete_vectors = everything
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.forget", decision="succeeded",
                         reason=f"removed_{len(removed)}_record(s)_and_vectors" if everything
                         else "removed_primary_record_only",
                         resource_type="memory", resource_id=memory_id)

    if not found:
        raise not_found()
    if delete_vectors:
        _apply_deletes(scope, removed)
    return Forgotten(memory_id=memory_id, forgotten=True)


# ------------------------------------------------------------------------------------------------
# confirm and summaries — the runtime's, not the model's
# ------------------------------------------------------------------------------------------------
@router.post("/{memory_id}/confirm", response_model=Confirmed, include_in_schema=False)
def confirm(memory_id: MemoryId, scope: Scope = Depends(request_scope)) -> Confirmed:
    """The user's explicit confirmation, delivered by the runtime. Not a tool the model has."""
    principal = scope.principal
    record = None
    with scope.services.db.transaction(principal) as cur:
        cur.execute(
            "UPDATE mem.records SET status = 'confirmed', confirmed_at = now(), "
            "confirmed_via = 'user' WHERE id = %s AND status = 'unconfirmed' "
            "RETURNING id, content, channel, status",
            (memory_id,),
        )
        row = cur.fetchone()
        if row is None:
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.confirm", decision="denied",
                         reason="not_visible_or_already_confirmed",
                         resource_type="memory", resource_id=memory_id)
        else:
            record = {"id": str(row["id"]), "content": row["content"], "status": row["status"],
                      "channel": row["channel"]}
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.confirm", decision="succeeded", reason="confirmed_by_user",
                         resource_type="memory", resource_id=memory_id)
            _enqueue(cur, principal.org_id, record["id"], "upsert")
    if record is None:
        raise not_found()
    _apply_upserts(scope, [record])
    return Confirmed(memory_id=memory_id, status="confirmed")


PENDING_PAGE = 10


class Pending(BaseModel):
    memory_id: str
    content: str
    channel: str
    created_at: str


class PendingList(BaseModel):
    pending: list[Pending] = Field(max_length=PENDING_PAGE)


@router.get("/pending", response_model=PendingList, include_in_schema=False)
def pending(scope: Scope = Depends(request_scope)) -> PendingList:
    """What is waiting for the user's confirmation, newest first — the runtime's confirmation screen.

    The caller's own, by row-level security, and only unconfirmed ones. Not a tool: a model that could
    list what awaits confirmation is one step from asking for it to be confirmed.
    """
    principal = scope.principal
    with scope.services.db.transaction(principal) as cur:
        cur.execute(
            "SELECT id, content, channel, created_at FROM mem.records WHERE status = 'unconfirmed' "
            "ORDER BY created_at DESC, id LIMIT %s",
            (PENDING_PAGE,),
        )
        rows = cur.fetchall()
        audit.record(cur, request_id=scope.request_id, principal=principal,
                     action="memory.pending.read", decision="allowed", reason=f"{len(rows)}_pending",
                     resource_type="memory")
    return PendingList(pending=[
        Pending(memory_id=str(r["id"]), content=r["content"], channel=r["channel"],
                created_at=r["created_at"].isoformat())
        for r in rows
    ])


@router.post("/{memory_id}/summaries", status_code=201, response_model=Summarised,
             include_in_schema=False)
def summarise(memory_id: MemoryId, scope: Scope = Depends(request_scope)) -> Summarised:
    """A derived record. Deterministic — no model — and it points at what it was made from.

    Summaries are how memory systems keep context small, and they are also how a memory survives
    being forgotten: the original goes, the summary made from it stays. `derived_from` is what lets
    `forget` find it.
    """
    principal = scope.principal
    record = None
    with scope.services.db.transaction(principal) as cur:
        cur.execute("SELECT id, content, status FROM mem.records WHERE id = %s", (memory_id,))
        source = cur.fetchone()
        if source is None:
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.summarise", decision="denied", reason="not_visible",
                         resource_type="memory", resource_id=memory_id)
        else:
            text = source["content"]
            content = "Summary of an earlier memory: " + (text if len(text) <= 160
                                                          else text[:157] + "...")
            cur.execute(
                "INSERT INTO mem.records (org_id, owner_sub, content, content_hash, channel, "
                "status, derived_from, confirmed_at, confirmed_via) VALUES "
                "(%s, %s, %s, %s, 'runtime', %s, %s, "
                " CASE WHEN %s = 'confirmed' THEN now() END, "
                " CASE WHEN %s = 'confirmed' THEN 'user' END) RETURNING id",
                (principal.org_id, principal.subject, content, _hash(content), source["status"],
                 memory_id, source["status"], source["status"]),
            )
            record = {"id": str(cur.fetchone()["id"]), "content": content,
                      "status": source["status"], "channel": "runtime"}
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="memory.summarise", decision="succeeded", reason="derived",
                         resource_type="memory", resource_id=record["id"])
            _enqueue(cur, principal.org_id, record["id"], "upsert")
    if record is None:
        raise not_found()
    _apply_upserts(scope, [record])
    return Summarised(memory_id=record["id"], derived_from=memory_id)


# ------------------------------------------------------------------------------------------------
# The outbox. Rows are written in the record's own transaction; they are applied to Qdrant after it
# commits. If Qdrant or the embedding model is down, the record is still written — memory-db is the
# source of truth — the row stays pending, and the reconciliation check names it.
# ------------------------------------------------------------------------------------------------
def _enqueue(cur, org_id: str, record_id: str, op: str) -> None:
    cur.execute("INSERT INTO mem.outbox (record_id, org_id, op) VALUES (%s, %s, %s)",
                (record_id, org_id, op))


def _mark_applied(scope: Scope, record_ids: list[str], op: str) -> None:
    with scope.services.db.transaction(scope.principal) as cur:
        cur.execute(
            "UPDATE mem.outbox SET applied_at = now() "
            "WHERE record_id = ANY(%s::uuid[]) AND op = %s AND applied_at IS NULL",
            (record_ids, op),
        )


def _apply_upserts(scope: Scope, records: list[dict]) -> None:
    extras = scope.services.extras
    if "vectors" not in extras or "embedder" not in extras:
        return
    try:
        for record in records:
            extras["vectors"].upsert(
                org_id=scope.principal.org_id, record_id=record["id"],
                vector=extras["embedder"].embed(record["content"]),
                payload={
                    "record_id": record["id"],
                    "owner_sub": scope.principal.subject,
                    "channel": record["channel"],
                    "status": record["status"],
                    "content_hash": _hash(record["content"]),
                    # The text is in the payload, as it is in most deployments. That is what makes
                    # the vector store a second copy of every memory rather than an index of ids —
                    # and what 9.6 and 9.8 show.
                    "content": record["content"],
                },
            )
        _mark_applied(scope, [r["id"] for r in records], "upsert")
    except ApiError:
        logger.warning("outbox_left_pending", extra={"op": "upsert", "count": len(records)})


def _apply_deletes(scope: Scope, record_ids: list[str]) -> None:
    extras = scope.services.extras
    if "vectors" not in extras:
        return
    try:
        extras["vectors"].delete(org_id=scope.principal.org_id, record_ids=record_ids)
        _mark_applied(scope, record_ids, "delete")
    except ApiError:
        logger.warning("outbox_left_pending", extra={"op": "delete", "count": len(record_ids)})
