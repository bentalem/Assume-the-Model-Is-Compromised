"""The add_internal_note tool.

The first tool that changes anything. Its request schema is where the "no model-supplied identity"
rule is most visible: there is no author field, and `extra="forbid"` means supplying one is a
rejected request rather than an ignored value — a silent ignore would leave the model believing it
had set an author.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import RequestScope, request_scope
from ..errors import conflict
from ..pipeline import ResourceContext
from ..repositories.notes import StaleTicketError

router = APIRouter(prefix="/v1", tags=["tickets"])

TICKET_NUMBER_PATTERN = r"^TKT-[0-9]{4,12}$"
MAX_NOTE_CHARS = 4000


class TicketStatus(str, Enum):
    open = "open"
    pending = "pending"
    resolved = "resolved"
    closed = "closed"


class CreateNoteRequest(BaseModel):
    """The request body.

    Note what is absent: author, organization, user id, timestamp. All are server-derived. With
    `extra="forbid"`, a model that tries to supply one gets a 400 rather than a quiet drop.
    """

    model_config = ConfigDict(extra="forbid")

    body: str = Field(
        min_length=1,
        max_length=MAX_NOTE_CHARS,
        description="The note text. Staff-only; never shown to the customer.",
    )
    expected_ticket_status: TicketStatus = Field(
        description=(
            "The ticket status the caller believes is current. The write is refused if the ticket "
            "has moved on, so a note is never attached to a ticket that changed underneath."
        )
    )


class CreateNoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_id: str
    created_at: datetime


@router.post(
    "/tickets/{ticket_number}/notes",
    operation_id="add_internal_note",
    summary="Add an internal note to a ticket",
    response_model=CreateNoteResponse,
    status_code=201,
    responses={
        400: {"description": "Invalid request"},
        401: {"description": "Unauthenticated"},
        404: {"description": "Not found or not allowed"},
        409: {"description": "The ticket changed; the note was not written"},
        503: {"description": "Service unavailable"},
    },
)
def add_internal_note(
    request: Request,
    scope: Annotated[RequestScope, Depends(request_scope)],
    ticket_number: Annotated[
        str,
        Path(
            pattern=TICKET_NUMBER_PATTERN,
            min_length=8,
            max_length=16,
            description="Ticket number in the form TKT-nnnn",
            examples=["TKT-1001"],
        ),
    ],
    payload: CreateNoteRequest,
) -> CreateNoteResponse:
    attributes = scope.tickets.lookup_attributes(
        ticket_number=ticket_number,
        organization_ids=scope.subject.organizations if scope.subject else [],
    )

    resource = (
        ResourceContext(
            type="ticket",
            id=attributes.ticket_number,
            organization_id=attributes.organization_id,
            attributes={
                "status": attributes.status,
                "assigned_team": attributes.assigned_team,
            },
        )
        if attributes
        else None
    )

    auth = scope.pipeline.authorize(
        request_id=scope.request_id,
        token=scope.token,
        subject=scope.subject,
        action="note.create",
        resource=resource,
        resource_type="ticket",
        resource_id=ticket_number,
    )

    try:
        note = scope.notes.create(
            request_id=scope.request_id,
            ticket_number=ticket_number,
            body=payload.body,
            expected_status=payload.expected_ticket_status.value,
            # Authorship from the verified subject. There is no path by which the request body
            # could reach this argument.
            user_id=auth.subject.user_id,
            organization_id=auth.organization_id,
            roles=auth.subject.roles_in(auth.organization_id),
            policy_version=auth.decision.policy_version,
            resource_id=ticket_number,
        )
    except StaleTicketError:
        raise conflict() from None

    # The success event is written inside the repository transaction, so nothing is recorded here.
    # The note body is never echoed back or logged.
    return CreateNoteResponse(note_id=note.note_id, created_at=note.created_at)
