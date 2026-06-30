"""BoardCompetitorsService — the editable S&P competitor reference list (R4).

Owner-only; no outbox, no shared search index.
"""
from __future__ import annotations

from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardCompetitorRecord,
    UpsertBoardCompetitorInput,
)
from ..repository import board_competitors as competitors_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


def _record_to_dict(c: BoardCompetitorRecord) -> dict[str, Any]:
    d = c.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


class BoardCompetitorsService:

    @staticmethod
    def to_payload(c: BoardCompetitorRecord) -> dict[str, Any]:
        return to_response(c)

    @staticmethod
    def list(ctx: ServiceContext, *, active_only: bool = False) -> list[BoardCompetitorRecord]:
        assert_owner(ctx, operation="list board competitors")
        return competitors_repo.list_competitors(ctx.conn, active_only=active_only)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> BoardCompetitorRecord:
        assert_owner(ctx, operation="read board competitor")
        c = competitors_repo.get_competitor_by_ulid(ctx.conn, ulid)
        if c is None:
            raise NotFoundError(f"board competitor not found: {ulid}")
        return c

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertBoardCompetitorInput) -> BoardCompetitorRecord:
        assert_owner(ctx, operation="upsert board competitor")
        with transaction(ctx.conn):
            existing = None
            if data.ulid:
                existing = competitors_repo.get_competitor_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = competitors_repo.get_competitor_by_name(ctx.conn, data.name)

            if existing is None:
                c = competitors_repo.insert_competitor(
                    ctx.conn,
                    name=data.name,
                    notes=data.notes,
                    active=True if data.active is None else data.active,
                    ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="board_competitor",
                    entity_id=c.id, entity_ulid=c.ulid, after=_record_to_dict(c),
                )
                return c

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid"})
            updated = competitors_repo.update_competitor_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_competitor",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated
