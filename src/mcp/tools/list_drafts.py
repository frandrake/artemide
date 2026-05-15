"""List outreach drafts."""
from __future__ import annotations

from pydantic import BaseModel

from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


class ListDraftsInput(BaseModel):
    partner_ulid: str | None = None
    status: str | None = None
    channel: str | None = None
    limit: int = 50


@mcp.tool
def list_drafts(payload: ListDraftsInput) -> dict:
    """List outreach drafts filtered by partner, status, or channel."""
    with tool_session("list_drafts") as (_, ctx):
        try:
            items = OutreachService.list_drafts(
                ctx,
                partner_ulid=payload.partner_ulid,
                status=payload.status,
                channel=payload.channel,
                limit=payload.limit,
            )
            return {"ok": True, "drafts": [r.model_dump(mode="json") for r in items]}
        except Exception as e:
            return error_response(e)
