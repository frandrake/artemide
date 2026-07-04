"""/api/v1/board/opportunities routes — board/NED seats, the gate, the evaluation."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    AdvanceBoardStageInput,
    BoardConflictCleared,
    BoardLinkedEntityType,
    BoardOppInterest,
    BoardOpportunityRecord,
    BoardOpportunityUpdateInput,
    BoardStage,
    RecordConflictScreenInput,
    SetBoardEvaluationInput,
    SetBoardOutcomeInput,
    UpsertBoardOpportunityInput,
)
from ..api._serde import to_response, to_response_list
from ..repository import board_conflict_screens as screens_repo
from ..repository import board_evaluations as evaluations_repo
from ..repository import board_opportunities as opportunities_repo
from ..services import ServiceContext
from ..services.board_conflict_service import BoardConflictService
from ..services.board_evaluation_service import BoardEvaluationService
from ..services.board_interactions_service import BoardInteractionsService
from ..services.board_opportunities_service import BoardOpportunitiesService
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/board/opportunities", tags=["board"])


def _detail(ctx: ServiceContext, o: BoardOpportunityRecord) -> dict[str, Any]:
    payload = BoardOpportunitiesService.to_payload(ctx, o)
    screen = screens_repo.get_by_opportunity(ctx.conn, o.id)
    payload["conflict_screen"] = to_response(screen, extra_exclude={"opportunity_id"}) if screen else None
    evaluation = evaluations_repo.get_by_opportunity(ctx.conn, o.id)
    payload["evaluation"] = to_response(evaluation, extra_exclude={"opportunity_id"}) if evaluation else None
    payload["log"] = to_response_list(
        opportunities_repo.list_log(ctx.conn, o.id), extra_exclude={"opportunity_id"}
    )
    payload["interactions"] = BoardInteractionsService.list_for_entity(
        ctx, BoardLinkedEntityType.board_opportunity, o.ulid
    )
    return payload


@router.get("")
def list_board_opportunities(
    stage: BoardStage | None = Query(default=None),
    interest: BoardOppInterest | None = Query(default=None),
    conflict_cleared: BoardConflictCleared | None = Query(default=None),
    sort: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    items = BoardOpportunitiesService.list(
        ctx, stage=stage, interest=interest, conflict_cleared=conflict_cleared, sort=sort
    )
    return [BoardOpportunitiesService.to_payload(ctx, o) for o in items]


@router.post("")
def upsert_board_opportunity(
    body: UpsertBoardOpportunityInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    o = BoardOpportunitiesService.upsert(ctx, body)
    payload = BoardOpportunitiesService.to_payload(ctx, o)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


# Literal sub-paths must be declared before /{ulid}.
@router.get("/evaluations/compare")
def compare_board_evaluations(
    ulid: list[str] = Query(default_factory=list),
    ctx: ServiceContext = Depends(get_context),
):
    return BoardEvaluationService.compare(ctx, ulid)


@router.get("/{ulid}")
def get_board_opportunity(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _detail(ctx, BoardOpportunitiesService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_board_opportunity(ulid: str, body: BoardOpportunityUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return BoardOpportunitiesService.to_payload(ctx, BoardOpportunitiesService.update_fields(ctx, ulid, body))


@router.post("/{ulid}/advance")
def advance_board_opportunity(ulid: str, body: AdvanceBoardStageInput, ctx: ServiceContext = Depends(get_context)):
    o, warnings = BoardOpportunitiesService.advance_stage(ctx, ulid, body)
    payload = BoardOpportunitiesService.to_payload(ctx, o)
    payload["warnings"] = warnings  # advisory R1 surfaces here
    return payload


@router.post("/{ulid}/outcome")
def set_board_opportunity_outcome(ulid: str, body: SetBoardOutcomeInput, ctx: ServiceContext = Depends(get_context)):
    return BoardOpportunitiesService.to_payload(ctx, BoardOpportunitiesService.set_outcome(ctx, ulid, body))


@router.post("/{ulid}/conflict-screen")
def record_board_conflict_screen(ulid: str, body: RecordConflictScreenInput, ctx: ServiceContext = Depends(get_context)):
    data = body.model_copy(update={"opportunity_ulid": ulid})
    BoardConflictService.record_screen(ctx, data)
    return _detail(ctx, BoardOpportunitiesService.get_by_ulid(ctx, ulid))


@router.get("/{ulid}/conflict-matches")
def board_conflict_matches(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardConflictService.suggest_competitor_matches(ctx, ulid)


@router.post("/{ulid}/evaluate")
def evaluate_board_opportunity(ulid: str, body: SetBoardEvaluationInput, ctx: ServiceContext = Depends(get_context)):
    data = body.model_copy(update={"opportunity_ulid": ulid})
    BoardEvaluationService.set_evaluation(ctx, data)
    return _detail(ctx, BoardOpportunitiesService.get_by_ulid(ctx, ulid))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board_opportunity(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    BoardOpportunitiesService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_board_opportunity(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardOpportunitiesService.to_payload(ctx, BoardOpportunitiesService.restore(ctx, ulid))
