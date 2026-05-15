"""Aggregate outreach metrics for the dashboard."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ...services.analytics_service import AnalyticsService
from .._common import error_response, tool_session
from ..registry import mcp


class OutreachMetricsInput(BaseModel):
    granularity: str | None = "week"   # day|week|month
    since: date | None = None
    until: date | None = None


@mcp.tool
def outreach_metrics(payload: OutreachMetricsInput) -> dict:
    """Return outreach volume, response rate, pipeline funnel, plan execution, and reciprocity totals."""
    with tool_session("outreach_metrics") as (_, ctx):
        try:
            return {
                "ok": True,
                "outreach_volume": AnalyticsService.outreach_volume(
                    ctx,
                    granularity=payload.granularity or "week",  # type: ignore[arg-type]
                    since=payload.since,
                    until=payload.until,
                ),
                "response_rate": AnalyticsService.response_rate(
                    ctx, since=payload.since, until=payload.until
                ),
                "plan_execution": AnalyticsService.plan_execution(
                    ctx, since=payload.since, until=payload.until
                ),
                "pipeline_funnel": AnalyticsService.pipeline_funnel(ctx),
            }
        except Exception as e:
            return error_response(e)
