"""Queue a proposed message (lands as 'proposed' for owner approval)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import ProposeMessageInput
from ...services.messages_service import MessagesService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def queue_message(payload: ProposeMessageInput) -> dict:
    """Propose a draft message. It is created as 'proposed' — never sent (Rule 17)."""
    with tool_session("queue_message") as (conn, ctx):
        try:
            m = MessagesService.propose(ctx, payload)
            return {"ok": True, "message": to_response(m, extra_exclude={"engagement_id"})}
        except Exception as e:
            return error_response(e)
