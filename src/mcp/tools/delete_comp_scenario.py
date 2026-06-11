"""Soft-delete a compensation scenario (owner-only)."""
from __future__ import annotations

from ...models import DeleteCompScenarioInput
from ...services.comp_service import CompService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def delete_comp_scenario(payload: DeleteCompScenarioInput) -> dict:
    """Soft-delete a compensation scenario. The baseline cannot be deleted —
    set another baseline first."""
    with tool_session("delete_comp_scenario") as (conn, ctx):
        try:
            CompService.soft_delete(ctx, payload.ulid)
            return {"ok": True, "deleted": payload.ulid}
        except Exception as e:
            return error_response(e)
