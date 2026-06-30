"""/api/v1/board/contacts routes — board individuals (partners, chairs, connectors)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    BoardContactUpdateInput,
    BoardLinkedEntityType,
    BoardRelationship,
    UpsertBoardContactInput,
)
from ..services import ServiceContext
from ..services.board_contacts_service import BoardContactsService
from ..services.board_interactions_service import BoardInteractionsService
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/board/contacts", tags=["board"])


@router.get("")
def list_board_contacts(
    firm_ulid: str | None = Query(default=None),
    relationship: BoardRelationship | None = Query(default=None),
    stale: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    items = BoardContactsService.list(
        ctx, firm_ulid=firm_ulid, relationship=relationship, stale_only=stale
    )
    return [BoardContactsService.to_payload(ctx, c) for c in items]


@router.post("")
def upsert_board_contact(
    body: UpsertBoardContactInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    c = BoardContactsService.upsert(ctx, body)
    payload = BoardContactsService.to_payload(ctx, c)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_board_contact(ulid: str, ctx: ServiceContext = Depends(get_context)):
    c = BoardContactsService.get_by_ulid(ctx, ulid)
    payload = BoardContactsService.to_payload(ctx, c)
    payload["interactions"] = BoardInteractionsService.list_for_entity(
        ctx, BoardLinkedEntityType.board_contact, c.ulid
    )
    return payload


@router.patch("/{ulid}")
def patch_board_contact(ulid: str, body: BoardContactUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return BoardContactsService.to_payload(ctx, BoardContactsService.update_fields(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board_contact(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    BoardContactsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_board_contact(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return BoardContactsService.to_payload(ctx, BoardContactsService.restore(ctx, ulid))
