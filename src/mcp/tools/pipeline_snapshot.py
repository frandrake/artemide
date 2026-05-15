"""Snapshot of the outreach Kanban — partners grouped by stage."""
from __future__ import annotations

from ...models import PipelineFilterInput
from ...services.pipeline_service import PipelineService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def pipeline_snapshot(payload: PipelineFilterInput) -> dict:
    """Return all partners bucketed by outreach_stage, with optional filters."""
    with tool_session("pipeline_snapshot") as (_, ctx):
        try:
            data = PipelineService.grouped_by_stage(ctx, payload)
            return {"ok": True, **data}
        except Exception as e:
            return error_response(e)
