"""ProgrammeService — milestones and the RAG slippage check (Rule 16)."""
from __future__ import annotations

import os
from datetime import date
from typing import Any

from ..models import (
    AuditAction,
    MilestoneUpdateInput,
    ProgrammeMilestoneRecord,
    ProgrammePhaseStatus,
    ProgrammeStatusResponse,
    RagStatus,
    UpsertMilestoneInput,
)
from ..repository import engagements as engagements_repo
from ..repository import partners as partners_repo
from ..repository import programme as programme_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


def _target_date() -> date:
    raw = os.environ.get("ARTEMIDE_PROGRAMME_TARGET_DATE", "2027-04-05")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date(2027, 4, 5)


def _today() -> date:
    return date.today()


def _record_to_dict(m: ProgrammeMilestoneRecord) -> dict[str, Any]:
    d = m.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


class ProgrammeService:

    # ---------- milestones ----------

    @staticmethod
    def list_milestones(ctx: ServiceContext) -> list[ProgrammeMilestoneRecord]:
        return programme_repo.list_milestones(ctx.conn)

    @staticmethod
    def upsert_milestone(ctx: ServiceContext, data: UpsertMilestoneInput) -> ProgrammeMilestoneRecord:
        assert_owner(ctx, operation="upsert milestone")
        with transaction(ctx.conn):
            existing = None
            if data.ulid:
                existing = programme_repo.get_milestone_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                m = programme_repo.insert_milestone(
                    ctx.conn, phase=data.phase, label=data.label, target_date=data.target_date,
                    status=data.status or "pending", metric_note=data.metric_note, ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="milestone",
                    entity_id=m.id, entity_ulid=m.ulid, after=_record_to_dict(m),
                )
                return m
            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid"})
            updated = programme_repo.update_milestone_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="milestone",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_milestone(ctx: ServiceContext, ulid: str, data: MilestoneUpdateInput) -> ProgrammeMilestoneRecord:
        assert_owner(ctx, operation="update milestone")
        with transaction(ctx.conn):
            m = programme_repo.get_milestone_by_ulid(ctx.conn, ulid)
            if m is None:
                raise NotFoundError(f"milestone not found: {ulid}")
            before = _record_to_dict(m)
            fields = data.model_dump(exclude_none=True)
            updated = programme_repo.update_milestone_fields(ctx.conn, m.id, fields) or m
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="milestone",
                entity_id=m.id, entity_ulid=m.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def reciprocity_suggestion(ctx: ServiceContext, engagement) -> str | None:
        """Rule 15: when a partner-sourced engagement advances, suggest (do not
        auto-write) a value_received note against that partner."""
        if getattr(engagement, "source_partner_id", None) is None:
            return None
        partner = partners_repo.get_partner_by_id(ctx.conn, engagement.source_partner_id)
        if partner is None:
            return None
        return (
            f"{partner.name} surfaced '{engagement.role_title}', now at "
            f"{engagement.stage.value}. Consider logging this as value received."
        )

    @staticmethod
    def note_offer_reached(ctx: ServiceContext) -> None:
        """Rule 14: reaching 'offer' nudges the close milestone toward done."""
        m = programme_repo.get_milestone_by_phase(ctx.conn, "close")
        if m is not None and m.status.value != "done":
            programme_repo.set_status(ctx.conn, m.id, "done")

    # ---------- status (Rule 16) ----------

    @staticmethod
    def days_to_target(ctx: ServiceContext | None = None) -> int:
        return (_target_date() - _today()).days

    @staticmethod
    def _seed_rag(ctx: ServiceContext) -> ProgrammePhaseStatus:
        warm = partners_repo.count_by_relationship_states(ctx.conn, ("warm", "warming"))
        if warm >= 5:
            rag = RagStatus.green
        elif warm >= 3:
            rag = RagStatus.amber
        else:
            rag = RagStatus.red
        return ProgrammePhaseStatus(phase="seed", rag=rag,
                                    detail=f"{warm} partner(s) at warm/warming (need ≥5)")

    @staticmethod
    def _run_rag(ctx: ServiceContext) -> ProgrammePhaseStatus:
        n = engagements_repo.count_at_stages(ctx.conn, ("formal", "final"))
        if n >= 2:
            rag = RagStatus.green
        elif n == 1:
            rag = RagStatus.amber
        else:
            rag = RagStatus.red
        return ProgrammePhaseStatus(phase="run", rag=rag,
                                    detail=f"{n} engagement(s) at formal/final (need ≥2)")

    @staticmethod
    def _close_rag(ctx: ServiceContext) -> ProgrammePhaseStatus:
        n = engagements_repo.count_at_stages(ctx.conn, ("offer", "decision"))
        rag = RagStatus.green if n >= 1 else RagStatus.red
        return ProgrammePhaseStatus(phase="close", rag=rag,
                                    detail=f"{n} engagement(s) at offer/decision (need ≥1)")

    @staticmethod
    def _milestone_rag(ctx: ServiceContext, phase: str) -> ProgrammePhaseStatus:
        m = programme_repo.get_milestone_by_phase(ctx.conn, phase)
        if m is None:
            return ProgrammePhaseStatus(phase=phase, rag=RagStatus.amber, detail="no milestone set")
        status_map = {
            "done": RagStatus.green, "on_track": RagStatus.green,
            "at_risk": RagStatus.amber, "pending": RagStatus.amber,
        }
        rag = status_map.get(m.status.value, RagStatus.amber)
        return ProgrammePhaseStatus(phase=phase, rag=rag, detail=m.metric_note or m.label)

    @staticmethod
    def status(ctx: ServiceContext) -> ProgrammeStatusResponse:
        phases = [
            ProgrammeService._milestone_rag(ctx, "build"),
            ProgrammeService._seed_rag(ctx),
            ProgrammeService._run_rag(ctx),
            ProgrammeService._close_rag(ctx),
            ProgrammeService._milestone_rag(ctx, "exit"),
        ]
        close = next(p for p in phases if p.phase == "close")
        target_at_risk = close.rag == RagStatus.red
        # overall: red if any red, else amber if any amber, else green.
        if any(p.rag == RagStatus.red for p in phases):
            overall = RagStatus.red
        elif any(p.rag == RagStatus.amber for p in phases):
            overall = RagStatus.amber
        else:
            overall = RagStatus.green
        return ProgrammeStatusResponse(
            days_to_target=ProgrammeService.days_to_target(ctx),
            target_date=_target_date(),
            overall_rag=overall,
            target_at_risk=target_at_risk,
            phases=phases,
        )
