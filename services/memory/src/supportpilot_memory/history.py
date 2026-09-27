"""Session history — the runtime's endpoints, not the model's.

An agent runtime records each turn of a conversation here and reads the tail back to build the next
context. None of these routes is in the model's action document: a model that could append turns
could write its own history, and one that could read sessions could go looking through other
people's. The same rule the lab already applies to the Range and the probe service.

Three properties worth reading the code for:

  * `authz` on every turn is captured from the verified principal at write time — the roles the
    caller held when the content was produced. It is never taken from the request. Context assembly
    re-checks it on replay (challenge 9.4).
  * Reading a transcript that is not your own is audited as such. With the quality-review setting
    off a colleague's session is simply not there; with it on, a manager can read it and the trail
    says who did (challenge 9.3).
  * A refusal is recorded and *then* refused. The audit row for a denial commits in its own right
    before the error is raised — raising inside the transaction would roll the evidence back with
    everything else, and a refused request would leave no trace at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from . import audit
from .dependencies import Scope, request_scope
from .errors import not_found
from .secrets_filter import contains_secret, filter_enabled, redact

router = APIRouter(prefix="/v1/sessions", tags=["runtime"], include_in_schema=False)

MAX_TURNS_PER_PAGE = 50
SessionId = Annotated[str, Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)


class SessionCreated(BaseModel):
    session_id: str


class AppendTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=8000)


class TurnAppended(BaseModel):
    session_id: str
    seq: int
    redacted: bool


class Turn(BaseModel):
    seq: int
    role: str
    content: str
    created_at: str


class Transcript(BaseModel):
    session_id: str
    # "owner" when you read your own session, "organisation" when you read a colleague's under the
    # quality-review setting. Never the other person's identity.
    read_as: Literal["owner", "organisation"]
    turns: list[Turn]
    next_cursor: int | None


@router.post("", status_code=201, response_model=SessionCreated)
def create_session(body: CreateSession, scope: Scope = Depends(request_scope)) -> SessionCreated:
    with scope.services.db.transaction(scope.principal) as cur:
        cur.execute(
            "INSERT INTO mem.sessions (org_id, owner_sub, title) VALUES (%s, %s, %s) RETURNING id",
            (scope.principal.org_id, scope.principal.subject, body.title),
        )
        session_id = str(cur.fetchone()["id"])
        audit.record(cur, request_id=scope.request_id, principal=scope.principal,
                     action="session.create", decision="succeeded", reason="created",
                     resource_type="session", resource_id=session_id)
    return SessionCreated(session_id=session_id)


@router.post("/{session_id}/turns", status_code=201, response_model=TurnAppended)
def append_turn(
    session_id: SessionId, body: AppendTurn, scope: Scope = Depends(request_scope)
) -> TurnAppended:
    principal = scope.principal
    appended: TurnAppended | None = None

    with scope.services.db.transaction(principal) as cur:
        # Your own session only. Under the quality-review setting a manager can *read* a colleague's
        # session; the turns_insert policy still refuses a write to it, and so does this check.
        cur.execute(
            "SELECT 1 FROM mem.sessions WHERE id = %s AND owner_sub = %s",
            (session_id, principal.subject),
        )
        if cur.fetchone() is None:
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="turn.append", decision="denied", reason="session_not_visible",
                         resource_type="session", resource_id=session_id)
        else:
            content = body.content
            redacted = filter_enabled(cur) and contains_secret(content)
            if redacted:
                content = redact(content)

            cur.execute(
                "SELECT coalesce(max(seq), 0) + 1 AS next FROM mem.turns WHERE session_id = %s",
                (session_id,),
            )
            seq = cur.fetchone()["next"]
            authz = {"roles": list(principal.roles), "at": datetime.now(UTC).isoformat()}
            cur.execute(
                "INSERT INTO mem.turns (session_id, org_id, owner_sub, seq, role, content, authz) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (session_id, principal.org_id, principal.subject, seq, body.role, content,
                 Jsonb(authz)),
            )
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="turn.append", decision="succeeded",
                         reason="redacted_secret" if redacted else "appended",
                         resource_type="session", resource_id=session_id)
            appended = TurnAppended(session_id=session_id, seq=seq, redacted=redacted)

    if appended is None:
        raise not_found()
    return appended


@router.get("/{session_id}/turns", response_model=Transcript)
def read_turns(
    session_id: SessionId,
    limit: Annotated[int, Query(ge=1, le=MAX_TURNS_PER_PAGE)] = 20,
    cursor: Annotated[int | None, Query(ge=0)] = None,
    scope: Scope = Depends(request_scope),
) -> Transcript:
    principal = scope.principal
    transcript: Transcript | None = None

    with scope.services.db.transaction(principal) as cur:
        # Row-level security decides visibility: your own session always, a colleague's only under
        # the quality-review setting and only as a manager. This query cannot see past that.
        cur.execute("SELECT owner_sub FROM mem.sessions WHERE id = %s", (session_id,))
        session = cur.fetchone()
        if session is None:
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="transcript.read", decision="denied", reason="not_visible",
                         resource_type="session", resource_id=session_id)
        else:
            read_as = "owner" if session["owner_sub"] == principal.subject else "organisation"
            cur.execute(
                "SELECT seq, role, content, created_at FROM mem.turns "
                "WHERE session_id = %s AND seq > %s ORDER BY seq LIMIT %s",
                (session_id, cursor or 0, limit + 1),
            )
            rows = cur.fetchall()
            audit.record(cur, request_id=scope.request_id, principal=principal,
                         action="transcript.read", decision="allowed",
                         reason="owner" if read_as == "owner" else "org_readable_manager",
                         resource_type="session", resource_id=session_id)
            page = rows[:limit]
            transcript = Transcript(
                session_id=session_id,
                read_as=read_as,
                turns=[Turn(seq=r["seq"], role=r["role"], content=r["content"],
                            created_at=r["created_at"].isoformat()) for r in page],
                next_cursor=page[-1]["seq"] if len(rows) > limit else None,
            )

    if transcript is None:
        raise not_found()
    return transcript
