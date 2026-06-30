"""/api/v1/board/firms routes — board search practices / platforms / networks."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ..models import BoardFirmStatus, BoardFirmUpdateInput, UpsertBoardFirmInput
from ..services import ServiceContext
from ..services.board_contacts_service import BoardContactsService
from ..services.board_firms_service import BoardFirmsService
from ..services.board_interactions_service import BoardInteractionsService
from ..models import BoardLinkedEntityType
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/board/firms", tags=["board"])


@router.get("")
def list_board_firms(
    status_filter: BoardFirmStatus | None = Query(default=None, alias="status"),
    tier: int | None = Query(default=None, ge=1, le=4),
    include_deleted: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    items = BoardFirmsService.list(ctx, status=status_filter, tier=tier, include_deleted=include_deleted)
    return [BoardFirmsService.to_payload(f) for f in items]


@router.post("")
def upsert_board_firm(
    body: UpsertBoardFirmInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    f = BoardFirmsService.upsert(ctx, body)
    payload = BoardFirmsService.to_payload(f)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_board_firm(ulid: str, ctx: ServiceContext = Depends(get_context)):
    f = BoardFirmsService.get_by_ulid(ctx, ulid)
    payload = BoardFirmsService.to_payload(f)
    payload["contacts"] = [
        BoardContactsService.to_payload(ctx, c)
        for c in BoardContactsService.list(ctx, firm_ulid=f.ulid)
    ]
    payload["interactions"] = BoardInteractionsService.list_for_entity(
        ctx, BoardLinkedEntityType.board_firm, f.ulid
    )
    return payload


@router.patch("/{ulid}")
def patch_board_firm(ulid: str, body: BoardFirmUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return BoardFirmsService.to_payload(BoardFirmsService.update_fields(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board_firm(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    BoardFirmsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_board_firm(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardFirmsService.to_payload(BoardFirmsService.restore(ctx, ulid))
