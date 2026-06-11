"""Attach or replace the verbatim transcript on an existing interview."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import SetTranscriptInput
from ...services.interviews_service import InterviewsService
from .._common import error_response, tool_session
from ..registry import mcp

_EXCLUDE = {"engagement_id", "engagement_log_id", "transcript"}


@mcp.tool
def set_transcript(payload: SetTranscriptInput) -> dict:
    """Set the transcript on an interview; the body becomes searchable."""
    with tool_session("set_transcript") as (conn, ctx):
        try:
            interview = InterviewsService.set_transcript(ctx, payload)
            return {"ok": True, "interview": to_response(interview, extra_exclude=_EXCLUDE)}
        except Exception as e:
            return error_response(e)
