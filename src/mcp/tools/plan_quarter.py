"""Generate a quarterly contact plan."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from ...models import PlanQuarterInput
from ...services.planning_service import PlanningService
from .._common import error_response, tool_session
from ..registry import mcp


def _slot(s) -> dict:
    d = asdict(s)
    if isinstance(d.get("week_starting"), date):
        d["week_starting"] = d["week_starting"].isoformat()
    return d


@mcp.tool
def plan_quarter(payload: PlanQuarterInput) -> dict:
    """Return the quarter topic plus suggested slots and gaps."""
    with tool_session("plan_quarter") as (_, ctx):
        try:
            plan = PlanningService.plan_quarter(
                ctx, year=payload.year, quarter=payload.quarter
            )
            return {
                "ok": True,
                "year": plan.year,
                "quarter": plan.quarter,
                "topic": plan.topic,
                "topic_status": plan.topic_status.value if plan.topic_status else None,
                "slots": [_slot(s) for s in plan.slots],
                "gaps": plan.gaps,
            }
        except Exception as e:
            return error_response(e)
