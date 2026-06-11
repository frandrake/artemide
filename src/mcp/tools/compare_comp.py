"""Compare compensation scenarios against the baseline (owner-only)."""
from __future__ import annotations

from ...models import CompareCompInput
from ...services.comp_service import CompService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def compare_comp(payload: CompareCompInput) -> dict:
    """Side-by-side comparison vs the baseline scenario. Returns per-field
    delta_gbp and delta_pct (pct is null when the baseline component is 0).
    Omit scenario_ulids to compare all live non-baseline scenarios."""
    with tool_session("compare_comp") as (conn, ctx):
        try:
            result = CompService.compare(
                ctx,
                scenario_ulids=payload.scenario_ulids,
                baseline_ulid=payload.baseline_ulid,
            )
            return {"ok": True, **result}
        except Exception as e:
            return error_response(e)
