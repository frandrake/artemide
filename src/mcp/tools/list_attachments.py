"""List attachments on an entity (metadata only)."""
from __future__ import annotations

from ...api._serde import to_response_list
from ...models import ListAttachmentsInput
from ...services.attachments_service import AttachmentsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def list_attachments(payload: ListAttachmentsInput) -> dict:
    """Return attachment metadata for a firm/partner/org/engagement/interview."""
    with tool_session("list_attachments") as (conn, ctx):
        try:
            items = AttachmentsService.list_by_entity(
                ctx, payload.entity_type, payload.entity_ulid
            )
            return {"ok": True, "attachments": to_response_list(items)}
        except Exception as e:
            return error_response(e)
