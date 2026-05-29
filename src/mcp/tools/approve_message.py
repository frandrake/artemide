"""Approve a proposed message — OWNER token only (Rule 17/18)."""
from __future__ import annotations

from ...api._serde import to_response
from ...services.messages_service import MessagesService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def approve_message(message_ulid: str) -> dict:
    """Approve a message, emitting message.approved. Bot-role tokens get 403."""
    with tool_session("approve_message") as (conn, ctx):
        try:
            m = MessagesService.approve(ctx, message_ulid)
            return {"ok": True, "message": to_response(m, extra_exclude={"engagement_id"})}
        except Exception as e:
            return error_response(e)
