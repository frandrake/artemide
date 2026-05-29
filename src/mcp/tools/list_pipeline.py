"""List the engagement pipeline grouped by stage, fit-sorted."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import ENGAGEMENT_STAGE_ORDER
from ...services.engagements_service import EngagementsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def list_pipeline() -> dict:
    """Return engagements grouped by stage (fit score descending within each)."""
    with tool_session("list_pipeline") as (conn, ctx):
        try:
            items = EngagementsService.list(ctx, sort="fit")
            groups: dict[str, list] = {s: [] for s in ENGAGEMENT_STAGE_ORDER}
            groups["closed"] = []
            for e in items:
                out = to_response(e, extra_exclude={"org_id", "source_partner_id"})
                groups.setdefault(e.stage.value, []).append(out)
            return {"ok": True, "pipeline": groups}
        except Exception as e:
            return error_response(e)
