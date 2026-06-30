"""BoardContactsService — individuals (partners, chairs, connectors).

Owner-only; no outbox, no shared search index. R5 (contact-move flag) is
computed here, never stored: a contact older than ~90 days is flagged
verify_before_send because people move between firms.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardContactRecord,
    BoardContactUpdateInput,
    UpsertBoardContactInput,
)
from ..repository import board_contacts as contacts_repo
from ..repository import board_firms as firms_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError

# R5 threshold — re-verify a contact whose last touch is older than this.
STALE_CONTACT_DAYS = 90


def _record_to_dict(c: BoardContactRecord) -> dict[str, Any]:
    d = c.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _verify_before_send(last_contact_date: date | None) -> bool:
    if last_contact_date is None:
        return True
    return (date.today() - last_contact_date).days > STALE_CONTACT_DAYS


class BoardContactsService:

    @staticmethod
    def to_payload(ctx: ServiceContext, c: BoardContactRecord) -> dict[str, Any]:
        payload = to_response(c)  # firm_id stripped by serde
        firm = firms_repo.get_firm_by_id(ctx.conn, c.firm_id) if c.firm_id is not None else None
        payload["firm_ulid"] = firm.ulid if firm else None
        payload["firm_name"] = firm.name if firm else None
        payload["verify_before_send"] = _verify_before_send(c.last_contact_date)
        return payload

    @staticmethod
    def _resolve_firm_id(ctx: ServiceContext, firm_ulid: str | None) -> int | None:
        if firm_ulid is None:
            return None
        firm = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
        if firm is None:
            raise NotFoundError(f"board firm not found: {firm_ulid}")
        return firm.id

    @staticmethod
    def list(
        ctx: ServiceContext, *, firm_ulid: str | None = None, relationship: Any = None,
        stale_only: bool = False,
    ) -> list[BoardContactRecord]:
        assert_owner(ctx, operation="list board contacts")
        firm_id = BoardContactsService._resolve_firm_id(ctx, firm_ulid)
        items = contacts_repo.list_contacts(ctx.conn, firm_id=firm_id, relationship=relationship)
        if stale_only:
            items = [c for c in items if _verify_before_send(c.last_contact_date)]
        return items

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> BoardContactRecord:
        assert_owner(ctx, operation="read board contact")
        c = contacts_repo.get_contact_by_ulid(ctx.conn, ulid)
        if c is None:
            raise NotFoundError(f"board contact not found: {ulid}")
        return c

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertBoardContactInput) -> BoardContactRecord:
        assert_owner(ctx, operation="upsert board contact")
        with transaction(ctx.conn):
            firm_id = BoardContactsService._resolve_firm_id(ctx, data.firm_ulid)

            existing = None
            if data.ulid:
                existing = contacts_repo.get_contact_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = contacts_repo.get_contact_by_name(ctx.conn, firm_id, data.name)

            if existing is None:
                c = contacts_repo.insert_contact(
                    ctx.conn,
                    name=data.name,
                    role_title=data.role_title,
                    firm_id=firm_id,
                    practice=data.practice,
                    email=data.email,
                    linkedin=data.linkedin,
                    mutual_connections=data.mutual_connections,
                    relationship=data.relationship or "cold",
                    last_contact_date=data.last_contact_date,
                    source_url=data.source_url,
                    notes=data.notes,
                    ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="board_contact",
                    entity_id=c.id, entity_ulid=c.ulid, after=_record_to_dict(c),
                )
                return c

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid", "firm_ulid"})
            if data.firm_ulid is not None:
                fields["firm_id"] = firm_id
            updated = contacts_repo.update_contact_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_contact",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: BoardContactUpdateInput) -> BoardContactRecord:
        assert_owner(ctx, operation="update board contact")
        with transaction(ctx.conn):
            c = BoardContactsService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            if "firm_ulid" in raw:
                raw["firm_id"] = BoardContactsService._resolve_firm_id(ctx, raw.pop("firm_ulid"))
            before = _record_to_dict(c)
            updated = contacts_repo.update_contact_fields(ctx.conn, c.id, raw) or c
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_contact",
                entity_id=c.id, entity_ulid=c.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete board contact")
        with transaction(ctx.conn):
            c = BoardContactsService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(c)
            contacts_repo.soft_delete_contact(ctx.conn, c.id)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="board_contact",
                entity_id=c.id, entity_ulid=c.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> BoardContactRecord:
        assert_owner(ctx, operation="restore board contact")
        with transaction(ctx.conn):
            c = contacts_repo.get_contact_by_ulid(ctx.conn, ulid)
            if c is None:
                raise NotFoundError(f"board contact not found: {ulid}")
            if c.deleted_at is None:
                return c
            contacts_repo.restore_contact(ctx.conn, c.id)
            restored = contacts_repo.get_contact_by_ulid(ctx.conn, ulid) or c
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="board_contact",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
