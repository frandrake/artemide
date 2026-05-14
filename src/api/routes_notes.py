"""/api/v1/notes routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..models import NoteEntityType
from ..services import ServiceContext
from ..services.exceptions import NotFoundError
from ..services.notes_service import NotesService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


class NoteInput(BaseModel):
    entity_type: NoteEntityType
    entity_ulid: str
    body: str


@router.get("")
def list_notes(
    entity_type: NoteEntityType = Query(...),
    entity_ulid: str = Query(...),
    ctx: ServiceContext = Depends(get_context),
):
    return to_response_list(NotesService.list_by_entity(ctx, entity_type, entity_ulid))


@router.post("")
def create_note(body: NoteInput, ctx: ServiceContext = Depends(get_context)):
    note = NotesService.create(
        ctx, entity_type=body.entity_type, entity_ulid=body.entity_ulid, body=body.body
    )
    return to_response(note)


@router.get("/{ulid}")
def get_note(ulid: str, ctx: ServiceContext = Depends(get_context)):
    note = NotesService.get_by_ulid(ctx, ulid)
    if note is None:
        raise NotFoundError(f"note not found: {ulid}")
    return to_response(note)
