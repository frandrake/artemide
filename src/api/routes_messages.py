"""/api/v1/messages routes — the approval queue (the human gate)."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query

from ..models import MessageEditInput, MessageRecord, MessageStatus, ProposeMessageInput
from ..repository import engagements as engagements_repo
from ..repository import partners as partners_repo
from ..services import ServiceContext
from ..services.messages_service import MessagesService
from ._serde import to_response
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])

_EXCLUDE = {"engagement_id"}  # partner_id already stripped by _serde


def _message_response(ctx: ServiceContext, m: MessageRecord) -> dict[str, Any]:
    payload = to_response(m, extra_exclude=_EXCLUDE)
    if m.partner_id is not None:
        partner = partners_repo.get_partner_by_id(ctx.conn, m.partner_id)
        payload["partner_ulid"] = partner.ulid if partner else None
        payload["partner_name"] = partner.name if partner else None
    else:
        payload["partner_ulid"] = None
    if m.engagement_id is not None:
        e = engagements_repo.get_engagement_by_id(ctx.conn, m.engagement_id)
        payload["engagement_ulid"] = e.ulid if e else None
    else:
        payload["engagement_ulid"] = None
    return payload


@router.get("")
def list_messages(
    status: MessageStatus | None = Query(default=None),
    partner_ulid: str | None = Query(default=None),
    engagement_ulid: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    items = MessagesService.list(
        ctx, status=status, partner_ulid=partner_ulid, engagement_ulid=engagement_ulid
    )
    return [_message_response(ctx, m) for m in items]


@router.post("")
def propose_message(
    body: ProposeMessageInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    m = MessagesService.propose(ctx, body)
    payload = _message_response(ctx, m)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_message(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _message_response(ctx, MessagesService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def edit_message(ulid: str, body: MessageEditInput, ctx: ServiceContext = Depends(get_context)):
    return _message_response(ctx, MessagesService.edit(ctx, ulid, body))


@router.post("/{ulid}/approve")
def approve_message(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _message_response(ctx, MessagesService.approve(ctx, ulid))


@router.post("/{ulid}/sent")
def mark_sent(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _message_response(ctx, MessagesService.mark_sent(ctx, ulid))


@router.post("/{ulid}/discard")
def discard_message(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _message_response(ctx, MessagesService.discard(ctx, ulid))
