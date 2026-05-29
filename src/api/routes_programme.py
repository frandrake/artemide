"""/api/v1/programme routes — milestones and RAG status."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import MilestoneUpdateInput, UpsertMilestoneInput
from ..services import ServiceContext
from ..services.programme_service import ProgrammeService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/programme", tags=["programme"])


@router.get("/status")
def programme_status(ctx: ServiceContext = Depends(get_context)):
    return ProgrammeService.status(ctx).model_dump(mode="json")


@router.get("/milestones")
def list_milestones(ctx: ServiceContext = Depends(get_context)):
    return to_response_list(ProgrammeService.list_milestones(ctx))


@router.post("/milestones")
def upsert_milestone(body: UpsertMilestoneInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(ProgrammeService.upsert_milestone(ctx, body))


@router.patch("/milestones/{ulid}")
def update_milestone(ulid: str, body: MilestoneUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(ProgrammeService.update_milestone(ctx, ulid, body))
