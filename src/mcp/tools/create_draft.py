"""Create an outreach draft. Auto-renders from template if body is empty."""
from __future__ import annotations

from ...models import OutreachDraftCreateInput
from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def create_draft(payload: OutreachDraftCreateInput) -> dict:
    """Create an outreach draft for a partner. If body is empty and template_ulid is given,
    the server renders the template using the partner's profile."""
    with tool_session("create_draft") as (_, ctx):
        try:
            rec = OutreachService.create_draft(ctx, payload)
            return {"ok": True, "draft": rec.model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
