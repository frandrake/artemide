"""Create or update a saved compensation scenario (owner-only)."""
from __future__ import annotations

from ...models import UpsertCompScenarioInput
from ...services.comp_service import CompService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def upsert_comp_scenario(payload: UpsertCompScenarioInput) -> dict:
    """Create or update a compensation scenario (matched by ulid or name).
    GBP integers; pension_pct is a percent of base. Totals are computed."""
    with tool_session("upsert_comp_scenario") as (conn, ctx):
        try:
            s = CompService.upsert(ctx, payload)
            return {"ok": True, "scenario": CompService.to_payload(ctx, s)}
        except Exception as e:
            return error_response(e)
