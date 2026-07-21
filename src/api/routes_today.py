"""Combined, labelled Today / next-best-action API."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from ..models import TodayFeedbackInput
from ..services import ServiceContext
from ..services.today_service import TodayService
from .deps import get_context

router = APIRouter(prefix="/api/v1/today", tags=["today"])


@router.get("")
def get_today(
    on_date: date | None = Query(default=None, alias="date"),
    ctx: ServiceContext = Depends(get_context),
):
    return TodayService.list_actions(ctx, on_date=on_date)


@router.post("/feedback")
def record_today_feedback(
    body: TodayFeedbackInput,
    ctx: ServiceContext = Depends(get_context),
):
    return TodayService.record_feedback(
        ctx,
        source_key=body.source_key,
        workstream=body.workstream.value,
        disposition=body.disposition.value,
        snoozed_until=body.snoozed_until,
        reason=body.reason,
    )
