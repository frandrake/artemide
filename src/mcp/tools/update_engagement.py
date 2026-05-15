"""Update an engagement-calendar entry (status, due_date, etc.)."""
from __future__ import annotations

from pydantic import BaseModel

from ...models import EngagementCalendarUpdateInput
from ...services.engagement_service import EngagementService
from .._common import error_response, tool_session
from ..registry import mcp


class UpdateEngagementInput(BaseModel):
    ulid: str
    update: EngagementCalendarUpdateInput


@mcp.tool
def update_engagement(payload: UpdateEngagementInput) -> dict:
    """Update an engagement-calendar entry. Use this to mark complete or reschedule."""
    with tool_session("update_engagement") as (_, ctx):
        try:
            rec = EngagementService.update(ctx, payload.ulid, payload.update)
            return {"ok": True, "engagement": rec.model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
