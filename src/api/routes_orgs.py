"""/api/v1/orgs routes."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ..models import NoteEntityType, OrgUpdateInput, ScaleBand, UpsertOrgInput, WatchState
from ..repository import engagements as engagements_repo
from ..repository import notes as notes_repo
from ..services import ServiceContext
from ..services.orgs_service import OrgsService
from ._serde import to_response, to_response_list
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/orgs", tags=["orgs"])

_ENG_EXCLUDE = {"org_id", "source_partner_id"}


@router.get("")
def list_orgs(
    watch_state: WatchState | None = Query(default=None),
    scale_band: ScaleBand | None = Query(default=None),
    sector: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return to_response_list(
        OrgsService.list(ctx, watch_state=watch_state, scale_band=scale_band, sector=sector)
    )


@router.post("")
def upsert_org(
    body: UpsertOrgInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    org = OrgsService.upsert(ctx, body)
    payload = to_response(org)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_org(ulid: str, ctx: ServiceContext = Depends(get_context)):
    org = OrgsService.get_by_ulid(ctx, ulid)
    engagements = engagements_repo.list_engagements(ctx.conn, org_id=org.id, sort="fit")
    notes = notes_repo.list_notes_by_entity(ctx.conn, NoteEntityType.org, org.ulid)
    payload = to_response(org)
    payload["engagements"] = to_response_list(engagements, extra_exclude=_ENG_EXCLUDE)
    payload["notes"] = to_response_list(notes)
    return payload


@router.patch("/{ulid}")
def patch_org(ulid: str, body: OrgUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(OrgsService.update_fields(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    OrgsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_org(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(OrgsService.restore(ctx, ulid))
