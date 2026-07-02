"""BoardTargetService — the NED-search goal and its progress read-out.

Owner-only, like every board service; no outbox, no shared search index.
The status() read-out is the board analogue of the exec programme_status:
seats won vs target, the open-opportunity funnel, and a simple documented RAG.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import (
    AuditAction,
    BoardOutcome,
    BoardTargetRecord,
    SetBoardTargetInput,
)
from ..repository import board_opportunities as opportunities_repo
from ..repository import board_target as target_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService

# Stage buckets for the RAG rule (open opportunities only).
_EARLY = {"surfaced", "conflict_screen"}
_MID = {"chair_meeting", "formal_process"}
_LATE = {"final_nomco", "offer", "decision"}

DEFAULT_SEATS_TARGET = 2


def _record_to_dict(t: BoardTargetRecord) -> dict[str, Any]:
    d = t.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def compute_board_rag(
    *,
    seats_won: int,
    seats_target: int,
    target_date: date | None,
    late: int,
    mid: int,
    today: date,
) -> str:
    """Documented RAG rule:

    - green — target met (seats_won >= seats_target).
    - red   — target date passed without meeting it, OR nothing beyond the
              early stages and nothing won.
    - amber — otherwise: something won, something late-stage, or ≥2 in the
              mid stages (a live-enough pipeline).
    """
    if seats_won >= seats_target:
        return "green"
    if target_date is not None and today > target_date:
        return "red"
    if seats_won >= 1 or late >= 1 or mid >= 2:
        return "amber"
    return "red"


class BoardTargetService:

    @staticmethod
    def get(ctx: ServiceContext) -> BoardTargetRecord | None:
        assert_owner(ctx, operation="read board target")
        return target_repo.get_target(ctx.conn)

    @staticmethod
    def set(ctx: ServiceContext, data: SetBoardTargetInput) -> BoardTargetRecord:
        assert_owner(ctx, operation="set board target")
        with transaction(ctx.conn):
            existing = target_repo.get_target(ctx.conn)
            before = _record_to_dict(existing) if existing else None
            target = target_repo.upsert_target(
                ctx.conn,
                seats_target=data.seats_target,
                target_date=data.target_date,
                notes=data.notes,
            )
            AuditService.record(
                ctx,
                action=AuditAction.update if existing else AuditAction.create,
                entity_type="board_target",
                entity_id=target.id,
                entity_ulid=target.ulid,
                before=before,
                after=_record_to_dict(target),
            )
            return target

    @staticmethod
    def status(ctx: ServiceContext) -> dict[str, Any]:
        assert_owner(ctx, operation="read board target status")
        today = date.today()
        target = target_repo.get_target(ctx.conn)
        seats_target = target.seats_target if target else DEFAULT_SEATS_TARGET
        target_date = target.target_date if target else None

        opportunities = opportunities_repo.list_opportunities(ctx.conn)
        seats_won = sum(1 for o in opportunities if o.outcome == BoardOutcome.accepted)
        open_opps = [
            o for o in opportunities
            if o.outcome is None and o.interest.value != "pass"
        ]
        funnel = {stage: 0 for stage in (*_EARLY, *_MID, *_LATE)}
        for o in open_opps:
            funnel[o.stage.value] = funnel.get(o.stage.value, 0) + 1
        late = sum(funnel[s] for s in _LATE)
        mid = sum(funnel[s] for s in _MID)
        early = sum(funnel[s] for s in _EARLY)

        return {
            "target_set": target is not None,
            "seats_target": seats_target,
            "target_date": target_date.isoformat() if target_date else None,
            "days_to_target": (target_date - today).days if target_date else None,
            "notes": target.notes if target else None,
            "seats_won": seats_won,
            "open_opportunities": len(open_opps),
            "funnel": {
                "surfaced": funnel["surfaced"],
                "conflict_screen": funnel["conflict_screen"],
                "chair_meeting": funnel["chair_meeting"],
                "formal_process": funnel["formal_process"],
                "final_nomco": funnel["final_nomco"],
                "offer": funnel["offer"],
                "decision": funnel["decision"],
            },
            "early": early,
            "mid": mid,
            "late": late,
            "rag": compute_board_rag(
                seats_won=seats_won,
                seats_target=seats_target,
                target_date=target_date,
                late=late,
                mid=mid,
                today=today,
            ),
        }
