"""List saved compensation scenarios (owner-only)."""
from __future__ import annotations

from ...models import ListCompScenariosInput
from ...repository import comp_scenarios as comp_repo
from ...services.comp_service import CompService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def list_comp_scenarios(payload: ListCompScenariosInput) -> dict:
    """List compensation scenarios (baseline first), optionally filtered by status."""
    with tool_session("list_comp_scenarios") as (conn, ctx):
        try:
            items = CompService.list(
                ctx, status=payload.status, include_deleted=payload.include_deleted
            )
            baseline = comp_repo.get_baseline(conn)
            return {
                "ok": True,
                "scenarios": [CompService.to_payload(ctx, s) for s in items],
                "baseline_ulid": baseline.ulid if baseline else None,
            }
        except Exception as e:
            return error_response(e)
