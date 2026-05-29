"""Programme RAG status and days-to-target."""
from __future__ import annotations

from ...services.programme_service import ProgrammeService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def programme_status() -> dict:
    """Return per-phase RAG, overall RAG, target_at_risk and days-to-target."""
    with tool_session("programme_status") as (conn, ctx):
        try:
            return {"ok": True, "status": ProgrammeService.status(ctx).model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
