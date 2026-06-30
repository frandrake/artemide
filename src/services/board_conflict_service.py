"""BoardConflictService — the conflict-of-interest screen (the gate).

Recording a screen maps its result onto the parent opportunity's
conflict_cleared flag (pass→yes, fail→no, pending→pending). R4: the screen can
be informed by the editable board_competitor reference list (S&P competitors).
Owner-only; no outbox, no shared search index.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardConflictResult,
    BoardConflictScreenRecord,
    BoardOppEventType,
    RecordConflictScreenInput,
)
from ..repository import board_competitors as competitors_repo
from ..repository import board_conflict_screens as screens_repo
from ..repository import board_opportunities as opportunities_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError

_RESULT_TO_CLEARED = {
    BoardConflictResult.pass_.value: "yes",
    BoardConflictResult.fail.value: "no",
    BoardConflictResult.pending.value: "pending",
}


class BoardConflictService:

    @staticmethod
    def get_for_opportunity(ctx: ServiceContext, opportunity_ulid: str) -> BoardConflictScreenRecord | None:
        assert_owner(ctx, operation="read board conflict screen")
        opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, opportunity_ulid)
        if opp is None:
            raise NotFoundError(f"board opportunity not found: {opportunity_ulid}")
        return screens_repo.get_by_opportunity(ctx.conn, opp.id)

    @staticmethod
    def record_screen(ctx: ServiceContext, data: RecordConflictScreenInput) -> BoardConflictScreenRecord:
        assert_owner(ctx, operation="record board conflict screen")
        with transaction(ctx.conn):
            opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, data.opportunity_ulid)
            if opp is None:
                raise NotFoundError(f"board opportunity not found: {data.opportunity_ulid}")

            screen = screens_repo.upsert_by_opportunity(
                ctx.conn,
                opportunity_id=opp.id,
                is_sp_competitor=data.is_sp_competitor,
                result=data.result,
                checked_date=data.checked_date or date.today(),
                notes=data.notes,
            )
            cleared = _RESULT_TO_CLEARED[data.result.value]
            opportunities_repo.set_conflict_cleared(ctx.conn, opp.id, cleared)
            opportunities_repo.insert_log(
                ctx.conn, opportunity_id=opp.id, event_date=date.today(),
                event_type=BoardOppEventType.conflict_screen,
                summary=f"conflict screen: {data.result.value} → conflict_cleared={cleared}",
            )
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_opportunity",
                entity_ulid=opp.ulid,
                after={
                    "conflict_cleared": cleared,
                    "result": data.result.value,
                    "is_sp_competitor": data.is_sp_competitor,
                },
            )
            return screen

    @staticmethod
    def suggest_competitor_matches(ctx: ServiceContext, opportunity_ulid: str) -> list[dict[str, Any]]:
        """R4: surface active S&P competitors whose name appears in the
        opportunity's organisation / source text — a hint for is_sp_competitor."""
        assert_owner(ctx, operation="match board competitors")
        opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, opportunity_ulid)
        if opp is None:
            raise NotFoundError(f"board opportunity not found: {opportunity_ulid}")
        haystack = " ".join(p for p in (opp.organisation, opp.source_text) if p).lower()
        matches = []
        for comp in competitors_repo.list_competitors(ctx.conn, active_only=True):
            if comp.name.lower() in haystack:
                matches.append(to_response(comp))
        return matches
