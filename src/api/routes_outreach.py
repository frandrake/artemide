"""/api/v1/outreach routes."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    OutreachChannel,
    OutreachDraftCreateInput,
    OutreachDraftUpdateInput,
    OutreachSendInput,
)
from ..repository import outreach as outreach_repo
from ..repository import partners as partners_repo
from ..services import ServiceContext
from ..services.outreach_service import OutreachService
from ._serde import to_response, to_response_list
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/outreach", tags=["outreach"])


# ---------- drafts ----------

@router.get("/drafts")
def list_drafts(
    partner_ulid: str | None = Query(default=None),
    status: str | None = Query(default=None),
    channel: OutreachChannel | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    ctx: ServiceContext = Depends(get_context),
):
    items = OutreachService.list_drafts(
        ctx,
        partner_ulid=partner_ulid,
        status=status,
        channel=channel.value if channel else None,
        limit=limit,
    )
    payloads = to_response_list(items)
    # The serializer strips partner_id; surface partner_ulid (batched) so the
    # global Drafts page can open the editor / render templates for the partner.
    partner_map = partners_repo.get_partners_by_ids(ctx.conn, [d.partner_id for d in items])
    for payload, draft in zip(payloads, items):
        p = partner_map.get(draft.partner_id)
        payload["partner_ulid"] = p.ulid if p else None
    return payloads


@router.post("/drafts")
def create_draft(
    body: OutreachDraftCreateInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    rec = OutreachService.create_draft(ctx, body)
    payload = to_response(rec)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/drafts/{ulid}")
def get_draft(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(OutreachService.get_draft(ctx, ulid))


@router.patch("/drafts/{ulid}")
def patch_draft(
    ulid: str, body: OutreachDraftUpdateInput, ctx: ServiceContext = Depends(get_context)
):
    return to_response(OutreachService.update_draft(ctx, ulid, body))


@router.post("/drafts/{ulid}/archive")
def archive_draft(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(OutreachService.archive_draft(ctx, ulid))


@router.get("/drafts/{ulid}/versions")
def list_draft_versions(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response_list(OutreachService.list_versions(ctx, ulid))


# ---------- messages (the send log) ----------

@router.post("/messages")
def send_draft(
    body: OutreachSendInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    result = OutreachService.mark_sent(ctx, body)
    store_idempotent_response(conn, idempotency_key, result, status_code=200)
    return result


@router.get("/messages")
def list_messages(
    partner_ulid: str | None = Query(default=None),
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    ctx: ServiceContext = Depends(get_context),
):
    partner_id = None
    if partner_ulid:
        from ..repository import partners as partners_repo
        p = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
        if p is None:
            from ..services.exceptions import NotFoundError
            raise NotFoundError(f"partner not found: {partner_ulid}")
        partner_id = p.id
    items = outreach_repo.list_messages(
        ctx.conn, partner_id=partner_id, since=since, until=until, limit=limit
    )
    return to_response_list(items)


@router.get("/messages/{ulid}")
def get_message(ulid: str, ctx: ServiceContext = Depends(get_context)):
    rec = outreach_repo.get_message_by_ulid(ctx.conn, ulid)
    if rec is None:
        from ..services.exceptions import NotFoundError
        raise NotFoundError(f"message not found: {ulid}")
    return to_response(rec)
