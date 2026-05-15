"""Set the outreach pipeline stage for a partner (Kanban move)."""
from __future__ import annotations

from pydantic import BaseModel

from ...models import OutreachStage
from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


class SetStageInput(BaseModel):
    partner_ulid: str
    stage: OutreachStage


@mcp.tool
def set_outreach_stage(payload: SetStageInput) -> dict:
    """Move a partner along the outreach pipeline. Stages:
    researched | drafted | sent | replied | met | ongoing | paused | dropped."""
    with tool_session("set_outreach_stage") as (_, ctx):
        try:
            rec = OutreachService.set_stage(ctx, payload.partner_ulid, payload.stage)
            return {"ok": True, "partner": rec.model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
