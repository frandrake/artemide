"""/api/v1/board/tasks routes — board-domain reminders / follow-ups."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ..models import BoardTaskStatus, BoardTaskUpdateInput, UpsertBoardTaskInput
from ..services import ServiceContext
from ..services.board_tasks_service import BoardTasksService
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/board/tasks", tags=["board"])


@router.get("")
def list_board_tasks(
    status_filter: BoardTaskStatus | None = Query(default=None, alias="status"),
    due_within_days: int | None = Query(default=None, ge=0),
    ctx: ServiceContext = Depends(get_context),
):
    items = BoardTasksService.list(ctx, status=status_filter, due_within_days=due_within_days)
    return [BoardTasksService.to_payload(t) for t in items]


@router.post("")
def upsert_board_task(
    body: UpsertBoardTaskInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    t = BoardTasksService.upsert(ctx, body)
    payload = BoardTasksService.to_payload(t)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_board_task(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardTasksService.to_payload(BoardTasksService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_board_task(ulid: str, body: BoardTaskUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return BoardTasksService.to_payload(BoardTasksService.update_fields(ctx, ulid, body))


@router.post("/{ulid}/done")
def complete_board_task(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardTasksService.to_payload(BoardTasksService.mark_done(ctx, ulid))
