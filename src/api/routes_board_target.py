"""/api/v1/board/target routes — the NED-search goal and its progress read-out."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import SetBoardTargetInput
from ..api._serde import to_response
from ..services import ServiceContext
from ..services.board_target_service import BoardTargetService
from .deps import get_context

router = APIRouter(prefix="/api/v1/board/target", tags=["board"])


@router.get("")
def get_board_target(ctx: ServiceContext = Depends(get_context)):
    target = BoardTargetService.get(ctx)
    return to_response(target) if target else None


@router.put("")
def set_board_target(body: SetBoardTargetInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(BoardTargetService.set(ctx, body))


@router.get("/status")
def board_target_status(ctx: ServiceContext = Depends(get_context)):
    return BoardTargetService.status(ctx)
