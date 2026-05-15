"""/api/v1/engagement-calendar routes."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ..models import EngagementCalendarUpdateInput, EngagementStatus
from ..services import ServiceContext
from ..services.engagement_service import EngagementService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/engagement-calendar", tags=["engagement"])


class RescheduleInput(BaseModel):
    due_date: date


@router.get("")
def list_engagements(
    status: EngagementStatus | None = Query(default=None),
    track: str | None = Query(default=None),
    due_window: str | None = Query(default=None),
    partner_ulid: str | None = Query(default=None),
    firm_ulid: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    items = EngagementService.list(
        ctx,
        status=status,
        track=track,
        due_window=due_window,  # type: ignore[arg-type]
        partner_ulid=partner_ulid,
        firm_ulid=firm_ulid,
    )
    return to_response_list(items)


@router.get("/{ulid}")
def get_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(EngagementService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_engagement(
    ulid: str, body: EngagementCalendarUpdateInput, ctx: ServiceContext = Depends(get_context)
):
    return to_response(EngagementService.update(ctx, ulid, body))


@router.post("/{ulid}/complete")
def complete_engagement(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(EngagementService.mark_complete(ctx, ulid))


@router.post("/{ulid}/reschedule")
def reschedule_engagement(
    ulid: str, body: RescheduleInput, ctx: ServiceContext = Depends(get_context)
):
    return to_response(EngagementService.reschedule(ctx, ulid, body.due_date))
