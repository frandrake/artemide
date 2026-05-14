"""Planning service. Cadence + quarterly spacing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from ..models import (
    AuditAction,
    CalendarStatus,
    FirmRecord,
    FirmTier,
    PartnerRecord,
    ValueCalendarRecord,
)
from ..repository import calendar as calendar_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


_CADENCE = {
    FirmTier.primary: {"ideal": 90, "overdue": 120, "dormancy": 180},
    FirmTier.specialist: {"ideal": 180, "overdue": 240, "dormancy": 365},
}


_SENIORITY_RANK = {"senior_partner": 4, "partner": 3, "associate_partner": 2, "principal": 1}


DueStatus = Literal["overdue", "due_soon", "no_planned_touch"]


@dataclass
class DueTouch:
    partner_ulid: str
    partner_name: str
    firm_ulid: str
    firm_name: str
    tier: str
    last_contact_date: date | None
    next_touch_date: date | None
    next_touch_topic: str | None
    days_since_last_contact: int | None
    days_until_next_touch: int | None
    status: DueStatus


@dataclass
class PlannedSlot:
    week_starting: date
    firm_ulid: str
    firm_name: str
    partner_ulid: str | None
    partner_name: str | None
    rationale: str


@dataclass
class QuarterPlan:
    year: int
    quarter: int
    topic: str | None
    topic_status: CalendarStatus | None
    slots: list[PlannedSlot] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


def _quarter_first_monday(year: int, quarter: int) -> date:
    start_month = {1: 1, 2: 4, 3: 7, 4: 10}[quarter]
    first = date(year, start_month, 1)
    offset = (7 - first.weekday()) % 7  # weekday 0=Mon
    return first + timedelta(days=offset) if first.weekday() != 0 else first


def _quarter_weeks(year: int, quarter: int) -> list[date]:
    start = _quarter_first_monday(year, quarter)
    return [start + timedelta(weeks=i) for i in range(13)]


def _partner_rank(p: PartnerRecord, today: date) -> tuple[int, int]:
    seniority_score = _SENIORITY_RANK.get((p.seniority or "").lower(), 0)
    if p.last_contact_date is None:
        overdue_days = 10_000
    else:
        overdue_days = (today - p.last_contact_date).days
    return (seniority_score, overdue_days)


class PlanningService:

    @staticmethod
    def list_due_touches(
        ctx: ServiceContext,
        *,
        window_days: int = 30,
        include_overdue: bool = True,
        tier: str = "all",
    ) -> list[DueTouch]:
        today = date.today()
        results: list[DueTouch] = []
        firms = firms_repo.list_firms(ctx.conn)
        for firm in firms:
            tier_str = firm.tier.value
            if tier != "all" and tier_str.lower() != tier.lower():
                continue
            if firm.tier == FirmTier.ned and tier.lower() != "ned":
                continue
            cadence = _CADENCE.get(firm.tier)
            if cadence is None:
                continue
            for p in partners_repo.list_partners_by_firm(ctx.conn, firm.id):
                days_since = (
                    (today - p.last_contact_date).days if p.last_contact_date else None
                )
                days_until = (
                    (p.next_touch_date - today).days if p.next_touch_date else None
                )
                status: DueStatus | None = None
                if days_since is not None and days_since >= cadence["overdue"]:
                    if include_overdue:
                        status = "overdue"
                elif days_until is not None and 0 <= days_until <= window_days:
                    status = "due_soon"
                elif p.next_touch_date is None and (
                    days_since is None or days_since >= cadence["ideal"]
                ):
                    status = "no_planned_touch"
                if status is None:
                    continue
                results.append(DueTouch(
                    partner_ulid=p.ulid,
                    partner_name=p.name,
                    firm_ulid=firm.ulid,
                    firm_name=firm.name,
                    tier=tier_str,
                    last_contact_date=p.last_contact_date,
                    next_touch_date=p.next_touch_date,
                    next_touch_topic=p.next_touch_topic,
                    days_since_last_contact=days_since,
                    days_until_next_touch=days_until,
                    status=status,
                ))

        def sort_key(d: DueTouch) -> tuple[int, int]:
            if d.status == "overdue":
                return (0, -(d.days_since_last_contact or 0))
            if d.status == "due_soon":
                return (1, d.days_until_next_touch or 0)
            return (2, -(d.days_since_last_contact or 0))

        results.sort(key=sort_key)
        return results

    @staticmethod
    def plan_quarter(
        ctx: ServiceContext, *, year: int, quarter: int
    ) -> QuarterPlan:
        today = date.today()
        topic_row = calendar_repo.get_quarter_topic(ctx.conn, year=year, quarter=quarter)
        plan = QuarterPlan(
            year=year,
            quarter=quarter,
            topic=topic_row.topic if topic_row else None,
            topic_status=topic_row.status if topic_row else None,
        )
        weeks = _quarter_weeks(year, quarter)
        used: set[date] = set()

        primary_firms = firms_repo.list_firms(ctx.conn, tier=FirmTier.primary)
        primary_firms.sort(key=lambda f: f.name)

        for firm in primary_firms:
            partners = partners_repo.list_partners_by_firm(ctx.conn, firm.id)
            if not partners:
                plan.gaps.append(firm.name)
                continue
            best = max(partners, key=lambda p: _partner_rank(p, today))
            slot_week = next((w for w in weeks if w not in used), None)
            if slot_week is None:
                plan.gaps.append(f"{firm.name} (no quarter capacity)")
                continue
            used.add(slot_week)
            rationale_bits = []
            if best.last_contact_date is None:
                rationale_bits.append("no prior contact on record")
            else:
                rationale_bits.append(
                    f"last contact {(today - best.last_contact_date).days}d ago"
                )
            if best.seniority:
                rationale_bits.append(f"seniority {best.seniority}")
            plan.slots.append(PlannedSlot(
                week_starting=slot_week,
                firm_ulid=firm.ulid,
                firm_name=firm.name,
                partner_ulid=best.ulid,
                partner_name=best.name,
                rationale="; ".join(rationale_bits),
            ))
        return plan

    @staticmethod
    def set_quarter_topic(
        ctx: ServiceContext,
        *,
        year: int,
        quarter: int,
        topic: str,
        status: CalendarStatus | None = None,
        notes: str | None = None,
    ) -> ValueCalendarRecord:
        with transaction(ctx.conn):
            existing = calendar_repo.get_quarter_topic(ctx.conn, year=year, quarter=quarter)
            before = existing.model_dump(mode="json") if existing else None
            record = calendar_repo.upsert_quarter_topic(
                ctx.conn,
                year=year,
                quarter=quarter,
                topic=topic,
                status=status or CalendarStatus.planned,
            )
            AuditService.record(
                ctx,
                action=AuditAction.plan,
                entity_type="value_calendar",
                entity_id=record.id,
                entity_ulid=record.ulid,
                before=before,
                after=record.model_dump(mode="json"),
            )
            return record

    @staticmethod
    def get_quarter_topic(
        ctx: ServiceContext, *, year: int, quarter: int
    ) -> ValueCalendarRecord | None:
        return calendar_repo.get_quarter_topic(ctx.conn, year=year, quarter=quarter)
