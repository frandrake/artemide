"""/api/v1/board/competitors routes — the editable S&P competitor reference list (R4)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ..models import UpsertBoardCompetitorInput
from ..services import ServiceContext
from ..services.board_competitors_service import BoardCompetitorsService
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/board/competitors", tags=["board"])


@router.get("")
def list_board_competitors(
    active_only: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    return [BoardCompetitorsService.to_payload(c) for c in BoardCompetitorsService.list(ctx, active_only=active_only)]


@router.post("")
def upsert_board_competitor(
    body: UpsertBoardCompetitorInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    c = BoardCompetitorsService.upsert(ctx, body)
    payload = BoardCompetitorsService.to_payload(c)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_board_competitor(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardCompetitorsService.to_payload(BoardCompetitorsService.get_by_ulid(ctx, ulid))
