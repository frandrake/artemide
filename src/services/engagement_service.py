"""Engagement calendar service. Surfaces the 12-month plan."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from ..models import (
    AuditAction,
    EngagementCalendarRecord,
    EngagementCalendarUpdateInput,
    EngagementStatus,
)
from ..repository import engagement_calendar as eng_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError


DueWindow = Literal["past_due", "this_week", "next_30", "next_90", "all"]


def _record_to_dict(rec: EngagementCalendarRecord) -> dict[str, Any]:
    d = rec.model_dump(mode="json")
    return {k: v for k, v in d.items() if k != "created_at"}


def _window_dates(window: DueWindow | None) -> tuple[date | None, date | None]:
    today = date.today()
    if window is None or window == "all":
        return None, None
    if window == "past_due":
        return None, today - timedelta(days=1)
    if window == "this_week":
        return today, today + timedelta(days=7)
    if window == "next_30":
        return today, today + timedelta(days=30)
    if window == "next_90":
        return today, today + timedelta(days=90)
    return None, None


class EngagementService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        status: EngagementStatus | str | None = None,
        track: str | None = None,
        due_window: DueWindow | None = None,
        partner_ulid: str | None = None,
        firm_ulid: str | None = None,
    ) -> list[EngagementCalendarRecord]:
        partner_id: int | None = None
        firm_id: int | None = None
        if partner_ulid:
            p = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if p is None:
                raise NotFoundError(f"partner not found: {partner_ulid}")
            partner_id = p.id
        if firm_ulid:
            f = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
            if f is None:
                raise NotFoundError(f"firm not found: {firm_ulid}")
            firm_id = f.id
        due_after, due_before = _window_dates(due_window)
        status_val = status.value if hasattr(status, "value") else status
        return eng_repo.list_engagements(
            ctx.conn,
            status=status_val,
            track=track,
            due_after=due_after,
            due_before=due_before,
            partner_id=partner_id,
            firm_id=firm_id,
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> EngagementCalendarRecord:
        rec = eng_repo.get_engagement_by_ulid(ctx.conn, ulid)
        if rec is None:
            raise NotFoundError(f"engagement not found: {ulid}")
        return rec

    @staticmethod
    def update(
        ctx: ServiceContext, ulid: str, data: EngagementCalendarUpdateInput
    ) -> EngagementCalendarRecord:
        with transaction(ctx.conn):
            rec = EngagementService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            before = _record_to_dict(rec)
            updated = eng_repo.update_engagement_fields(ctx.conn, rec.id, raw)
            assert updated is not None
            AuditService.record(
                ctx,
                action=AuditAction.plan,
                entity_type="engagement_calendar",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def mark_complete(ctx: ServiceContext, ulid: str) -> EngagementCalendarRecord:
        return EngagementService.update(
            ctx, ulid, EngagementCalendarUpdateInput(status=EngagementStatus.complete)
        )

    @staticmethod
    def reschedule(
        ctx: ServiceContext, ulid: str, new_date: date
    ) -> EngagementCalendarRecord:
        return EngagementService.update(
            ctx, ulid, EngagementCalendarUpdateInput(due_date=new_date)
        )
