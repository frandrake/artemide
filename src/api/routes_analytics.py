"""/api/v1/analytics routes."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from ..services import ServiceContext
from ..services.analytics_service import AnalyticsService
from .deps import get_context

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/outreach-volume")
def outreach_volume(
    granularity: str = Query(default="week", pattern="^(day|week|month)$"),
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return {
        "granularity": granularity,
        "buckets": AnalyticsService.outreach_volume(
            ctx, granularity=granularity, since=since, until=until  # type: ignore[arg-type]
        ),
    }


@router.get("/response-rate")
def response_rate(
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return AnalyticsService.response_rate(ctx, since=since, until=until)


@router.get("/reciprocity-balance")
def reciprocity_balance(ctx: ServiceContext = Depends(get_context)):
    return AnalyticsService.reciprocity_per_partner(ctx)


@router.get("/plan-execution")
def plan_execution(
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return AnalyticsService.plan_execution(ctx, since=since, until=until)


@router.get("/pipeline-funnel")
def pipeline_funnel(ctx: ServiceContext = Depends(get_context)):
    return AnalyticsService.pipeline_funnel(ctx)
