"""/api/v1/board/interactions routes — the board activity log + outreach-due."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..api._serde import to_response
from ..models import BoardLinkedEntityType, LogBoardInteractionInput
from ..services import ServiceContext
from ..services.board_interactions_service import BoardInteractionsService
from .deps import get_context

router = APIRouter(prefix="/api/v1/board/interactions", tags=["board"])


@router.get("/due")
def list_board_interactions_due(
    within_days: int = Query(default=14, ge=0),
    ctx: ServiceContext = Depends(get_context),
):
    return BoardInteractionsService.list_due(ctx, within_days=within_days)


@router.get("")
def list_board_interactions_for_entity(
    entity_type: BoardLinkedEntityType = Query(...),
    entity_ulid: str = Query(...),
    ctx: ServiceContext = Depends(get_context),
):
    items = BoardInteractionsService.list_for_entity(ctx, entity_type, entity_ulid)
    return [to_response(i) for i in items]


@router.post("")
def log_board_interaction(body: LogBoardInteractionInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(BoardInteractionsService.log_interaction(ctx, body))
