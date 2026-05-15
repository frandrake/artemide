"""Mark a draft as sent. Atomically writes contact_log + outreach_message + stage."""
from __future__ import annotations

from ...models import OutreachSendInput
from ...services.outreach_service import OutreachService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def mark_sent(payload: OutreachSendInput) -> dict:
    """Mark an outreach draft as sent. Writes the contact_log entry, advances stage,
    and freezes the message in the immutable outreach_message log. Atomic."""
    with tool_session("mark_sent") as (_, ctx):
        try:
            return {"ok": True, **OutreachService.mark_sent(ctx, payload)}
        except Exception as e:
            return error_response(e)
