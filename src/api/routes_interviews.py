"""Interview routes — structured interviews + transcripts on an engagement.

Two prefixes share this router: engagement-scoped collection endpoints under
/api/v1/engagements/{ulid}/interviews and item endpoints under
/api/v1/interviews/{ulid}.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from datetime import date

from ..models import (
    InterviewFormat,
    InterviewRecord,
    InterviewUpdateInput,
    LogInterviewInput,
    SetTranscriptInput,
    TranscriptSource,
)
from ..repository import engagements as engagements_repo
from ..services import ServiceContext
from ..services.interviews_service import InterviewsService
from ._serde import to_response
from .deps import get_context

router = APIRouter(tags=["interviews"])

_BASE_EXCLUDE = {"engagement_id", "engagement_log_id"}


class LogInterviewBody(BaseModel):
    # engagement_ulid comes from the path, not the body.
    interview_date: date
    round: str | None = None
    format: InterviewFormat | None = None
    panel: str | None = None
    summary: str | None = None
    transcript: str | None = None
    transcript_source: TranscriptSource | None = None


class TranscriptBody(BaseModel):
    transcript: str
    transcript_source: TranscriptSource = TranscriptSource.manual


def _interview_response(
    ctx: ServiceContext, rec: InterviewRecord, *, include_transcript: bool = False
) -> dict[str, Any]:
    exclude = set(_BASE_EXCLUDE)
    if not include_transcript:
        exclude.add("transcript")
    payload = to_response(rec, extra_exclude=exclude)
    engagement = engagements_repo.get_engagement_by_id(ctx.conn, rec.engagement_id)
    payload["engagement_ulid"] = engagement.ulid if engagement else None
    return payload


@router.post("/api/v1/engagements/{ulid}/interviews")
def log_interview(ulid: str, body: LogInterviewBody, ctx: ServiceContext = Depends(get_context)):
    # The path ulid is authoritative for which engagement this belongs to.
    data = LogInterviewInput(engagement_ulid=ulid, **body.model_dump())
    rec = InterviewsService.log(ctx, data)
    return _interview_response(ctx, rec, include_transcript=bool(rec.transcript))


@router.get("/api/v1/engagements/{ulid}/interviews")
def list_interviews(ulid: str, ctx: ServiceContext = Depends(get_context)):
    items = InterviewsService.list_by_engagement(ctx, ulid)
    return [_interview_response(ctx, rec) for rec in items]


@router.get("/api/v1/interviews/{ulid}")
def get_interview(
    ulid: str,
    include_transcript: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    rec = InterviewsService.get(ctx, ulid, include_transcript=include_transcript)
    return _interview_response(ctx, rec, include_transcript=include_transcript)


@router.patch("/api/v1/interviews/{ulid}")
def patch_interview(ulid: str, body: InterviewUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return _interview_response(ctx, InterviewsService.update_fields(ctx, ulid, body))


@router.put("/api/v1/interviews/{ulid}/transcript")
def put_transcript(ulid: str, body: TranscriptBody, ctx: ServiceContext = Depends(get_context)):
    data = SetTranscriptInput(
        interview_ulid=ulid,
        transcript=body.transcript,
        transcript_source=body.transcript_source,
    )
    rec = InterviewsService.set_transcript(ctx, data)
    return _interview_response(ctx, rec, include_transcript=True)


@router.delete("/api/v1/interviews/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    InterviewsService.soft_delete(ctx, ulid)


@router.post("/api/v1/interviews/{ulid}/restore")
def restore_interview(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return _interview_response(ctx, InterviewsService.restore(ctx, ulid))
