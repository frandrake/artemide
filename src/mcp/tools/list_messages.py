"""List the approval queue (proposed messages by default)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import MessageStatus
from ...services.messages_service import MessagesService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def list_messages(status: MessageStatus = MessageStatus.proposed) -> dict:
    """List messages by status (default 'proposed' — the approval queue)."""
    with tool_session("list_messages") as (conn, ctx):
        try:
            items = MessagesService.list(ctx, status=status)
            return {"ok": True, "messages": [to_response(m, extra_exclude={"engagement_id"}) for m in items]}
        except Exception as e:
            return error_response(e)
