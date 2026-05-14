"""List partners with due or overdue touches."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from ...models import ListDueTouchesInput
from ...services.planning_service import PlanningService
from .._common import error_response, tool_session
from ..registry import mcp


def _asdict(obj):
    d = asdict(obj)
    for k, v in list(d.items()):
        if isinstance(v, date):
            d[k] = v.isoformat()
    return d


@mcp.tool
def list_due_touches(payload: ListDueTouchesInput) -> dict:
    """Return partners flagged as overdue, due-soon, or with no planned touch."""
    with tool_session("list_due_touches") as (_, ctx):
        try:
            tier = payload.tier.value if payload.tier else "all"
            items = PlanningService.list_due_touches(
                ctx, window_days=payload.window_days, include_overdue=True, tier=tier
            )
            return {"ok": True, "due_touches": [_asdict(d) for d in items]}
        except Exception as e:
            return error_response(e)
