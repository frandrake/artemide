"""Update an outreach draft. Bumps version when subject or body changes."""
from __future__ import annotations

from pydantic import BaseModel

from ...models import OutreachDraftUpdateInput
from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


class UpdateDraftInput(BaseModel):
    draft_ulid: str
    update: OutreachDraftUpdateInput


@mcp.tool
def update_draft(payload: UpdateDraftInput) -> dict:
    """Update an outreach draft. Bumps the version if subject or body changes."""
    with tool_session("update_draft") as (_, ctx):
        try:
            rec = OutreachService.update_draft(ctx, payload.draft_ulid, payload.update)
            return {"ok": True, "draft": rec.model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
