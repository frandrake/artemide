"""Set the value-exchange topic for a given (year, quarter)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import SetQuarterTopicInput
from ...services.planning_service import PlanningService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def set_quarter_topic(payload: SetQuarterTopicInput) -> dict:
    """Upsert the topic + status for one quarter."""
    with tool_session("set_quarter_topic") as (_, ctx):
        try:
            record = PlanningService.set_quarter_topic(
                ctx,
                year=payload.year,
                quarter=payload.quarter,
                topic=payload.topic,
                status=payload.status,
            )
            return {"ok": True, "quarter": to_response(record)}
        except Exception as e:
            return error_response(e)
