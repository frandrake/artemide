"""Advance an engagement's stage (forward-only, Rule 14)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import AdvanceStageInput, EngagementStage
from ...services.engagements_service import EngagementsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def advance_engagement(engagement_ulid: str, to_stage: EngagementStage, summary: str | None = None) -> dict:
    """Move an engagement forward to the given stage, logging the change."""
    with tool_session("advance_engagement") as (conn, ctx):
        try:
            e = EngagementsService.advance_stage(
                ctx, engagement_ulid, AdvanceStageInput(to_stage=to_stage, summary=summary)
            )
            return {"ok": True, "engagement": to_response(e, extra_exclude={"org_id", "source_partner_id"})}
        except Exception as e:
            return error_response(e)
