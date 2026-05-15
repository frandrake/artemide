"""/api/v1/pipeline routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models import FirmTier, PipelineFilterInput
from ..services import ServiceContext
from ..services.pipeline_service import PipelineService
from .deps import get_context

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("")
def pipeline_snapshot(
    tier: FirmTier | None = Query(default=None),
    strategic_relevance: str | None = Query(default=None),
    ned_gateway: bool | None = Query(default=None),
    track: str | None = Query(default=None),
    ctx: ServiceContext = Depends(get_context),
):
    return PipelineService.grouped_by_stage(
        ctx,
        PipelineFilterInput(
            tier=tier,
            strategic_relevance=strategic_relevance,
            ned_gateway=ned_gateway,
            track=track,
        ),
    )
