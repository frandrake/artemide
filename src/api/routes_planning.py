"""/api/v1/planning routes."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..models import CalendarStatus
from ..services import ServiceContext
from ..services.planning_service import PlanningService
from ._serde import to_response
from .deps import get_context

router = APIRouter(prefix="/api/v1/planning", tags=["planning"])


class QuarterTopicInput(BaseModel):
    year: int
    quarter: int
    topic: str
    status: CalendarStatus | None = None
    notes: str | None = None


def _asdict(obj):
    d = asdict(obj)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@router.get("/due-touches")
def due_touches(
    window_days: int = Query(default=30, ge=0, le=365),
    include_overdue: bool = Query(default=True),
    tier: str = Query(default="all"),
    ctx: ServiceContext = Depends(get_context),
):
    items = PlanningService.list_due_touches(
        ctx, window_days=window_days, include_overdue=include_overdue, tier=tier
    )
    return [_asdict(d) for d in items]


@router.get("/quarter")
def get_quarter(
    year: int = Query(...),
    quarter: int = Query(..., ge=1, le=4),
    ctx: ServiceContext = Depends(get_context),
):
    plan = PlanningService.plan_quarter(ctx, year=year, quarter=quarter)
    return {
        "year": plan.year,
        "quarter": plan.quarter,
        "topic": plan.topic,
        "topic_status": plan.topic_status.value if plan.topic_status else None,
        "slots": [_asdict(s) for s in plan.slots],
        "gaps": plan.gaps,
    }


@router.post("/quarter-topic")
def set_quarter_topic(
    body: QuarterTopicInput, ctx: ServiceContext = Depends(get_context)
):
    record = PlanningService.set_quarter_topic(
        ctx, year=body.year, quarter=body.quarter,
        topic=body.topic, status=body.status, notes=body.notes,
    )
    return to_response(record)
