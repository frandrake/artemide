"""/api/v1/comp-scenarios routes — saved packages and baseline comparison."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    CompScenarioStatus,
    CompScenarioUpdateInput,
    UpsertCompScenarioInput,
)
from ..services import ServiceContext
from ..services.comp_service import CompService
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/comp-scenarios", tags=["comp"])


@router.get("")
def list_comp_scenarios(
    status_filter: CompScenarioStatus | None = Query(default=None, alias="status"),
    include_deleted: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    items = CompService.list(ctx, status=status_filter, include_deleted=include_deleted)
    return [CompService.to_payload(ctx, s) for s in items]


@router.post("")
def upsert_comp_scenario(
    body: UpsertCompScenarioInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    s = CompService.upsert(ctx, body)
    payload = CompService.to_payload(ctx, s)
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


# Literal path must be declared before /{ulid}.
@router.get("/compare")
def compare_comp(
    scenario_ulid: list[str] | None = Query(default=None),
    baseline_ulid: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return CompService.compare(
        ctx, scenario_ulids=scenario_ulid, baseline_ulid=baseline_ulid
    )


@router.get("/{ulid}")
def get_comp_scenario(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return CompService.to_payload(ctx, CompService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_comp_scenario(
    ulid: str, body: CompScenarioUpdateInput, ctx: ServiceContext = Depends(get_context)
):
    return CompService.to_payload(ctx, CompService.update_fields(ctx, ulid, body))


@router.post("/{ulid}/baseline")
def set_comp_baseline(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return CompService.to_payload(ctx, CompService.set_baseline(ctx, ulid))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comp_scenario(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    CompService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_comp_scenario(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return CompService.to_payload(ctx, CompService.restore(ctx, ulid))
