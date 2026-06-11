"""List interviews on an engagement (metadata — no transcripts)."""
from __future__ import annotations

from ...api._serde import to_response_list
from ...models import ListInterviewsInput
from ...services.interviews_service import InterviewsService
from .._common import error_response, tool_session
from ..registry import mcp

_EXCLUDE = {"engagement_id", "engagement_log_id", "transcript"}


@mcp.tool
def list_interviews(payload: ListInterviewsInput) -> dict:
    """Return the interview timeline for an engagement (transcripts omitted)."""
    with tool_session("list_interviews") as (conn, ctx):
        try:
            items = InterviewsService.list_by_engagement(ctx, payload.engagement_ulid)
            return {"ok": True, "interviews": to_response_list(items, extra_exclude=_EXCLUDE)}
        except Exception as e:
            return error_response(e)
