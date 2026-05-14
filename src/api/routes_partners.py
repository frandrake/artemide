"""/api/v1/partners routes."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ..models import RelationshipState
from ..repository import firms as firms_repo
from ..services import ServiceContext
from ..services.partners_service import PartnersService
from ._serde import to_response, to_response_list
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/partners", tags=["partners"])


class PartnerUpsert(BaseModel):
    firm_name: str
    name: str
    title: str | None = None
    practice: str | None = None
    seniority: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relationship_state: RelationshipState | None = None
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    notes_summary: str | None = None


class PartnerPatch(BaseModel):
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    follow_ups: list[str] | None = None


@router.get("")
def list_partners(
    firm_ulid: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    if firm_ulid:
        return to_response_list(PartnersService.list_by_firm(ctx, firm_ulid))
    out = []
    for firm in firms_repo.list_firms(ctx.conn):
        out.extend(PartnersService.list_by_firm(ctx, firm.ulid))
    return to_response_list(out)


@router.get("/{ulid}")
def get_partner(ulid: str, ctx: ServiceContext = Depends(get_context)):
    pwf = PartnersService.get_by_ulid(ctx, ulid)
    partner = to_response(pwf.partner)
    partner["firm_ulid"] = pwf.firm.ulid
    partner["firm_name"] = pwf.firm.name
    return partner


@router.post("")
def upsert_partner(
    body: PartnerUpsert,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    fields = body.model_dump(exclude={"firm_name", "name"}, exclude_none=True)
    partner = PartnersService.upsert(ctx, body.firm_name, body.name, **fields)
    payload = to_response(partner)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.patch("/{ulid}")
def patch_partner(
    ulid: str, patch: PartnerPatch, ctx: ServiceContext = Depends(get_context)
):
    partner = PartnersService.get_by_ulid(ctx, ulid).partner
    if patch.next_touch_date is not None or patch.next_touch_topic is not None:
        partner = PartnersService.update_planned_touch(
            ctx, ulid, patch.next_touch_date, patch.next_touch_topic
        )
    if patch.follow_ups is not None:
        partner = PartnersService.update_follow_ups(ctx, ulid, patch.follow_ups)
    return to_response(partner)


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    PartnersService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_partner(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(PartnersService.restore(ctx, ulid))
