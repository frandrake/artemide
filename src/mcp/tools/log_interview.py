"""Log a structured interview (and optional transcript) on an engagement."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import LogInterviewInput
from ...services.interviews_service import InterviewsService
from .._common import error_response, tool_session
from ..registry import mcp

_EXCLUDE = {"engagement_id", "engagement_log_id", "transcript"}


@mcp.tool
def log_interview(payload: LogInterviewInput) -> dict:
    """Record an interview for an engagement, writing the paired timeline event.

    The transcript (if supplied) is stored and indexed for search but omitted
    from this response; fetch it via get_interview(include_transcript=true).
    """
    with tool_session("log_interview") as (conn, ctx):
        try:
            interview = InterviewsService.log(ctx, payload)
            return {"ok": True, "interview": to_response(interview, extra_exclude=_EXCLUDE)}
        except Exception as e:
            return error_response(e)
