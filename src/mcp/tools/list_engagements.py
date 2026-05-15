"""List 12-month engagement calendar entries."""
from __future__ import annotations

from pydantic import BaseModel

from ...services.engagement_service import EngagementService
from .._common import error_response, tool_session
from ..registry import mcp


class ListEngagementsInput(BaseModel):
    status: str | None = None
    track: str | None = None
    due_window: str | None = None     # past_due | this_week | next_30 | next_90 | all
    partner_ulid: str | None = None
    firm_ulid: str | None = None


@mcp.tool
def list_engagements(payload: ListEngagementsInput) -> dict:
    """Return engagement-calendar rows filtered by status, track, due window, partner, or firm."""
    with tool_session("list_engagements") as (_, ctx):
        try:
            items = EngagementService.list(
                ctx,
                status=payload.status,
                track=payload.track,
                due_window=payload.due_window,  # type: ignore[arg-type]
                partner_ulid=payload.partner_ulid,
                firm_ulid=payload.firm_ulid,
            )
            return {
                "ok": True,
                "engagements": [r.model_dump(mode="json") for r in items],
            }
        except Exception as e:
            return error_response(e)
