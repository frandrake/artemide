"""Notes service. Free-form notes attached to firms or partners."""
from __future__ import annotations

from ..models import AuditAction, NoteEntityType, NoteRecord
from ..repository import firms as firms_repo
from ..repository import notes as notes_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


def _resolve(ctx: ServiceContext, entity_type: NoteEntityType, entity_ulid: str) -> str:
    if entity_type == NoteEntityType.firm:
        firm = firms_repo.get_firm_by_ulid(ctx.conn, entity_ulid)
        if firm is None:
            raise NotFoundError(f"firm not found: {entity_ulid}")
        return f"{entity_type.value}:{firm.name}"
    partner = partners_repo.get_partner_by_ulid(ctx.conn, entity_ulid)
    if partner is None:
        raise NotFoundError(f"partner not found: {entity_ulid}")
    return f"{entity_type.value}:{partner.name}"


class NotesService:

    @staticmethod
    def create(
        ctx: ServiceContext,
        *,
        entity_type: NoteEntityType,
        entity_ulid: str,
        body: str,
    ) -> NoteRecord:
        with transaction(ctx.conn):
            label = _resolve(ctx, entity_type, entity_ulid)
            note = notes_repo.insert_note(
                ctx.conn,
                entity_type=entity_type,
                entity_id=entity_ulid,
                body=body,
            )
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="note",
                entity_ulid=note.ulid,
                primary_text=label,
                secondary_text=body,
            )
            AuditService.record(
                ctx,
                action=AuditAction.note,
                entity_type="note",
                entity_id=note.id,
                entity_ulid=note.ulid,
                before=None,
                after=note.model_dump(mode="json"),
            )
            return note

    @staticmethod
    def list_by_entity(
        ctx: ServiceContext, entity_type: NoteEntityType, entity_ulid: str
    ) -> list[NoteRecord]:
        return notes_repo.list_notes_by_entity(ctx.conn, entity_type, entity_ulid)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> NoteRecord | None:
        return notes_repo.get_note_by_ulid(ctx.conn, ulid)
