"""BoardTasksService — board-domain reminders / follow-ups.

Owner-only; no outbox, no shared search index. Board tasks appear only in board
views (they live in their own table).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardLinkedEntityType,
    BoardTaskRecord,
    BoardTaskStatus,
    BoardTaskUpdateInput,
    UpsertBoardTaskInput,
)
from ..repository import board_contacts as contacts_repo
from ..repository import board_firms as firms_repo
from ..repository import board_opportunities as opportunities_repo
from ..repository import board_tasks as tasks_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError


def _record_to_dict(t: BoardTaskRecord) -> dict[str, Any]:
    d = t.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


class BoardTasksService:

    @staticmethod
    def to_payload(t: BoardTaskRecord) -> dict[str, Any]:
        return to_response(t)

    @staticmethod
    def _validate_linked(ctx: ServiceContext, entity_type: BoardLinkedEntityType | None, ulid: str | None) -> None:
        if entity_type is None or ulid is None:
            return
        if entity_type == BoardLinkedEntityType.board_firm:
            ent = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
        elif entity_type == BoardLinkedEntityType.board_contact:
            ent = contacts_repo.get_contact_by_ulid(ctx.conn, ulid)
        else:
            ent = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid)
        if ent is None:
            raise NotFoundError(f"{entity_type.value} not found: {ulid}")

    @staticmethod
    def list(
        ctx: ServiceContext, *, status: Any = None, due_within_days: int | None = None
    ) -> list[BoardTaskRecord]:
        assert_owner(ctx, operation="list board tasks")
        due_on_or_before = (
            date.today() + timedelta(days=max(0, due_within_days))
            if due_within_days is not None
            else None
        )
        return tasks_repo.list_tasks(ctx.conn, status=status, due_on_or_before=due_on_or_before)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> BoardTaskRecord:
        assert_owner(ctx, operation="read board task")
        t = tasks_repo.get_task_by_ulid(ctx.conn, ulid)
        if t is None:
            raise NotFoundError(f"board task not found: {ulid}")
        return t

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertBoardTaskInput) -> BoardTaskRecord:
        assert_owner(ctx, operation="upsert board task")
        with transaction(ctx.conn):
            BoardTasksService._validate_linked(ctx, data.linked_entity_type, data.linked_entity_ulid)
            existing = tasks_repo.get_task_by_ulid(ctx.conn, data.ulid) if data.ulid else None

            if existing is None:
                t = tasks_repo.insert_task(
                    ctx.conn,
                    title=data.title,
                    linked_entity_type=data.linked_entity_type,
                    linked_entity_ulid=data.linked_entity_ulid,
                    due_date=data.due_date,
                    status=data.status or "open",
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="board_task",
                    entity_id=t.id, entity_ulid=t.ulid, after=_record_to_dict(t),
                )
                return t

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid"})
            updated = tasks_repo.update_task_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_task",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: BoardTaskUpdateInput) -> BoardTaskRecord:
        assert_owner(ctx, operation="update board task")
        with transaction(ctx.conn):
            t = BoardTasksService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            BoardTasksService._validate_linked(
                ctx, data.linked_entity_type, data.linked_entity_ulid
            )
            before = _record_to_dict(t)
            updated = tasks_repo.update_task_fields(ctx.conn, t.id, raw) or t
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_task",
                entity_id=t.id, entity_ulid=t.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def mark_done(ctx: ServiceContext, ulid: str) -> BoardTaskRecord:
        assert_owner(ctx, operation="complete board task")
        with transaction(ctx.conn):
            t = BoardTasksService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(t)
            tasks_repo.set_status(ctx.conn, t.id, BoardTaskStatus.done)
            updated = tasks_repo.get_task_by_ulid(ctx.conn, ulid) or t
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_task",
                entity_id=t.id, entity_ulid=t.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated
