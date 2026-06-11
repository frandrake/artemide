"""Fetch one interview, optionally including the full transcript."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import GetInterviewInput
from ...services.interviews_service import InterviewsService
from .._common import error_response, tool_session
from ..registry import mcp

_BASE_EXCLUDE = {"engagement_id", "engagement_log_id"}


@mcp.tool
def get_interview(payload: GetInterviewInput) -> dict:
    """Return an interview; set include_transcript=true for the verbatim body."""
    with tool_session("get_interview") as (conn, ctx):
        try:
            interview = InterviewsService.get(
                ctx, payload.interview_ulid, include_transcript=payload.include_transcript
            )
            exclude = set(_BASE_EXCLUDE)
            if not payload.include_transcript:
                exclude.add("transcript")
            return {"ok": True, "interview": to_response(interview, extra_exclude=exclude)}
        except Exception as e:
            return error_response(e)
