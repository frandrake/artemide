"""Preparation-pack APIs and side-effect-free notification queue transport."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ..services import ServiceContext
from ..services.notification_service import NotificationService
from ..services.preparation_service import PreparationService
from .deps import get_context, require_owner

router = APIRouter(prefix="/api/v1", tags=["preparation-notifications"])


class SourceInput(BaseModel):
    source_kind: str
    source_ulid: str | None = None
    public_url: str | None = None
    sha256: str
    retrieved_at: str
    citation_label: str


class ExecutivePackInput(BaseModel):
    target_entity_type: str
    target_entity_ulid: str
    content: str
    sources: list[SourceInput]
    generated_by: str
    model: str | None = None
    prompt_version: str | None = None
    generation_metadata: dict[str, Any] | None = None


class BoardPackInput(BaseModel):
    board_opportunity_ulid: str
    content: str
    sources: list[SourceInput]
    generated_by: str
    model: str | None = None
    prompt_version: str | None = None
    generation_metadata: dict[str, Any] | None = None


class NotificationInput(BaseModel):
    notification_type: str
    priority: Literal["P1", "P2", "P3"]
    dedupe_key: str
    payload: dict[str, Any]
    now: datetime
    expires_at: datetime
    not_before: datetime | None = None


class SentInput(BaseModel):
    sent_at: datetime


@router.post("/preparation/executive", status_code=status.HTTP_201_CREATED)
def propose_executive_pack(body: ExecutivePackInput, ctx: ServiceContext = Depends(require_owner)):
    values = body.model_dump()
    values["sources"] = [source.model_dump() for source in body.sources]
    return PreparationService.propose_executive(ctx, **values)


@router.get("/preparation/executive")
def list_executive_packs(target_entity_type: str, target_entity_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.list_executive(ctx, target_entity_type=target_entity_type, target_entity_ulid=target_entity_ulid)


@router.get("/preparation/executive/{pack_ulid}")
def get_executive_pack(pack_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.get_executive(ctx, pack_ulid)


@router.post("/preparation/executive/{pack_ulid}/confirm")
def confirm_executive_pack(pack_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.confirm_executive(ctx, pack_ulid)


@router.post("/preparation/board", status_code=status.HTTP_201_CREATED)
def propose_board_pack(body: BoardPackInput, ctx: ServiceContext = Depends(require_owner)):
    values = body.model_dump()
    values["sources"] = [source.model_dump() for source in body.sources]
    return PreparationService.propose_board(ctx, **values)


@router.get("/preparation/board")
def list_board_packs(board_opportunity_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.list_board(ctx, board_opportunity_ulid=board_opportunity_ulid)


@router.get("/preparation/board/{pack_ulid}")
def get_board_pack(pack_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.get_board(ctx, pack_ulid)


@router.post("/preparation/board/{pack_ulid}/confirm")
def confirm_board_pack(pack_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PreparationService.confirm_board(ctx, pack_ulid)


@router.post("/notifications/queue", status_code=status.HTTP_201_CREATED)
def queue_notification(body: NotificationInput, ctx: ServiceContext = Depends(get_context)):
    row = NotificationService.queue(ctx, **body.model_dump())
    return {**row, "payload": json.loads(row["payload"])}


@router.get("/notifications/eligible")
def eligible_notifications(now: datetime, limit: int = Query(default=50, ge=1, le=500), ctx: ServiceContext = Depends(get_context)):
    rows = NotificationService.list_eligible(ctx, now=now, limit=limit)
    return [{**row, "payload": json.loads(row["payload"])} for row in rows]


@router.post("/notifications/{dispatch_ulid}/sent")
def mark_notification_sent(dispatch_ulid: str, body: SentInput, ctx: ServiceContext = Depends(get_context)):
    return {"changed": NotificationService.mark_sent(ctx, dispatch_ulid, sent_at=body.sent_at)}
