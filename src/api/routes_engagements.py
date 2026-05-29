"""/api/v1/engagements routes — the pipeline."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    AdvanceStageInput,
    CloseEngagementInput,
    EngagementInterest,
    EngagementRecord,
    EngagementStage,
    EngagementUpdateInput,
    NoteEntityType,
    UpsertEngagementInput,
)
from ..repository import engagements as engagements_repo
from ..repository import notes as notes_repo
from ..repository import orgs as orgs_repo
from ..repository import partners as partners_repo
from ..services import ServiceContext
from ..services.engagements_service import EngagementsService
from ._serde import to_response, to_response_list
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/engagements", tags=["engagements"])

_EXCLUDE = {"org_id", "source_partner_id"}


def _engagement_response(ctx: ServiceContext, e: EngagementRecord) -> dict[str, Any]:
    payload = to_response(e, extra_exclude=_EXCLUDE)
    org = orgs_repo.get_org_by_id(ctx.conn, e.org_id)
    payload["org_ulid"] = org.ulid if org else None
    payload["org_name"] = org.name if org else None
    if e.source_partner_id is not None:
        partner = partners_repo.get_partner_by_id(ctx.conn, e.source_partner_id)
        payload["source_partner_ulid"] = partner.ulid if partner else None
        payload["source_partner_name"] = partner.name if partner else None
    else:
        payload["source_partner_ulid"] = None
        payload["source_partner_name"] = None
    if e.fit_breakdown:
        try:
            payload["fit_breakdown"] = json.loads(e.fit_breakdown)
        except ValueError:
            pass
    return payload


@router.get("")
def list_engagements(
    stage: EngagementStage | None = Query(default=None),
    interest: EngagementInterest | None = Query(default=None),
    org_ulid: str | None = Query(default=None),
    partner_ulid: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    items = EngagementsService.list(
        ctx, stage=stage, interest=interest, org_ulid=org_ulid,
        source_partner_ulid=partner_ulid, sort=sort,
    )
    return [_engagement_response(ctx, e) for e in items]


@router.post("")
def upsert_engagement(
    body: UpsertEngagementInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    e = EngagementsService.upsert(ctx, body)
    payload = _engagement_response(ctx, e)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)):
    e = EngagementsService.get_by_ulid(ctx, ulid)
    payload = _engagement_response(ctx, e)
    payload["log"] = to_response_list(engagements_repo.list_log(ctx.conn, e.id))
    payload["notes"] = to_response_list(
        notes_repo.list_notes_by_entity(ctx.conn, NoteEntityType.engagement, e.ulid)
    )
    return payload


@router.patch("/{ulid}")
def patch_engagement(ulid: str, body: EngagementUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return _engagement_response(ctx, EngagementsService.update_fields(ctx, ulid, body))


@router.post("/{ulid}/advance")
def advance_engagement(ulid: str, body: AdvanceStageInput, ctx: ServiceContext = Depends(get_context)):
    return _engagement_response(ctx, EngagementsService.advance_stage(ctx, ulid, body))


@router.post("/{ulid}/close")
def close_engagement(ulid: str, body: CloseEngagementInput, ctx: ServiceContext = Depends(get_context)):
    return _engagement_response(ctx, EngagementsService.close(ctx, ulid, body))


@router.post("/{ulid}/rescore")
def rescore_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _engagement_response(ctx, EngagementsService.rescore(ctx, ulid))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    EngagementsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _engagement_response(ctx, EngagementsService.restore(ctx, ulid))
