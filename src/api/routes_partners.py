"""/api/v1/partners routes."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ..models import OutreachStage, PartnerUpdateInput, RelationshipState
from pydantic import BaseModel as _BaseModel
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
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


@router.get("")
def list_partners(
    firm_ulid: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    if firm_ulid:
        firm = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
        if firm is None:
            from ..services.exceptions import NotFoundError
            raise NotFoundError(f"firm not found: {firm_ulid}")
        return to_response_list(
            partners_repo.list_partners_by_firm(ctx.conn, firm.id, include_deleted=include_deleted)
        )
    out = []
    for firm in firms_repo.list_firms(ctx.conn):
        out.extend(partners_repo.list_partners_by_firm(ctx.conn, firm.id, include_deleted=include_deleted))
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
def patch_partner(ulid: str, body: PartnerUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(PartnersService.update_fields(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    PartnersService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_partner(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(PartnersService.restore(ctx, ulid))


class _OutreachStageInput(_BaseModel):
    stage: OutreachStage


@router.post("/{ulid}/outreach-stage")
def set_outreach_stage(
    ulid: str, body: _OutreachStageInput, ctx: ServiceContext = Depends(get_context)
):
    from ..services.outreach_service import OutreachService
    return to_response(OutreachService.set_stage(ctx, ulid, body.stage))
