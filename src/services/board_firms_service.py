"""BoardFirmsService — the board search practices / platforms / networks.

Owner-only on every method (board is the more confidential domain); no outbox,
no shared search index (R0 separation — board never enters the FTS corpus or the
event stream).
"""
from __future__ import annotations

from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardFirmRecord,
    BoardFirmUpdateInput,
    UpsertBoardFirmInput,
)
from ..repository import board_firms as firms_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError


def _record_to_dict(f: BoardFirmRecord) -> dict[str, Any]:
    d = f.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


class BoardFirmsService:

    @staticmethod
    def to_payload(f: BoardFirmRecord) -> dict[str, Any]:
        return to_response(f)

    @staticmethod
    def list(
        ctx: ServiceContext, *, status: Any = None, tier: int | None = None,
        include_deleted: bool = False,
    ) -> list[BoardFirmRecord]:
        assert_owner(ctx, operation="list board firms")
        return firms_repo.list_firms(ctx.conn, status=status, tier=tier, include_deleted=include_deleted)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> BoardFirmRecord:
        assert_owner(ctx, operation="read board firm")
        f = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
        if f is None:
            raise NotFoundError(f"board firm not found: {ulid}")
        return f

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertBoardFirmInput) -> BoardFirmRecord:
        assert_owner(ctx, operation="upsert board firm")
        with transaction(ctx.conn):
            existing = None
            if data.ulid:
                existing = firms_repo.get_firm_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = firms_repo.get_firm_by_name(ctx.conn, data.name)

            if existing is None:
                f = firms_repo.insert_firm(
                    ctx.conn,
                    name=data.name,
                    firm_type=data.firm_type,
                    geography=data.geography,
                    sectors_level=data.sectors_level,
                    ai_on_boards_hook=data.ai_on_boards_hook,
                    tier=data.tier,
                    status=data.status or "to_approach",
                    next_action=data.next_action,
                    notes=data.notes,
                    source_url=data.source_url,
                    ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="board_firm",
                    entity_id=f.id, entity_ulid=f.ulid, after=_record_to_dict(f),
                )
                return f

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid"})
            updated = firms_repo.update_firm_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_firm",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: BoardFirmUpdateInput) -> BoardFirmRecord:
        assert_owner(ctx, operation="update board firm")
        with transaction(ctx.conn):
            f = BoardFirmsService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            before = _record_to_dict(f)
            updated = firms_repo.update_firm_fields(ctx.conn, f.id, raw) or f
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_firm",
                entity_id=f.id, entity_ulid=f.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete board firm")
        with transaction(ctx.conn):
            f = BoardFirmsService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(f)
            firms_repo.soft_delete_firm(ctx.conn, f.id)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="board_firm",
                entity_id=f.id, entity_ulid=f.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> BoardFirmRecord:
        assert_owner(ctx, operation="restore board firm")
        with transaction(ctx.conn):
            f = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
            if f is None:
                raise NotFoundError(f"board firm not found: {ulid}")
            if f.deleted_at is None:
                return f
            firms_repo.restore_firm(ctx.conn, f.id)
            restored = firms_repo.get_firm_by_ulid(ctx.conn, ulid) or f
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="board_firm",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
