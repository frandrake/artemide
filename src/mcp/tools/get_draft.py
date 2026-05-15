"""Get one outreach draft (head version)."""
from __future__ import annotations

from pydantic import BaseModel

from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


class GetDraftInput(BaseModel):
    draft_ulid: str


@mcp.tool
def get_draft(payload: GetDraftInput) -> dict:
    """Get an outreach draft by ULID (head version + version count)."""
    with tool_session("get_draft") as (_, ctx):
        try:
            rec = OutreachService.get_draft(ctx, payload.draft_ulid)
            versions = OutreachService.list_versions(ctx, payload.draft_ulid)
            return {
                "ok": True,
                "draft": rec.model_dump(mode="json"),
                "versions_count": len(versions),
            }
        except Exception as e:
            return error_response(e)
