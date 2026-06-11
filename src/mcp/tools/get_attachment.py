"""Fetch attachment metadata + base64 content (for small files only)."""
from __future__ import annotations

import base64

from ...api._serde import to_response
from ...models import GetAttachmentInput
from ...services.attachments_service import AttachmentsService
from .._common import error_response, tool_session
from ..registry import mcp

# Tighter than the service's 25 MB cap: keep tool responses small.
_MCP_CONTENT_CEILING = 4 * 1024 * 1024


@mcp.tool
def get_attachment(payload: GetAttachmentInput) -> dict:
    """Return attachment metadata; includes base64 content when <= 4 MB."""
    with tool_session("get_attachment") as (conn, ctx):
        try:
            rec = AttachmentsService.get_metadata(ctx, payload.attachment_ulid)
            result: dict = {"ok": True, "attachment": to_response(rec)}
            if rec.byte_size <= _MCP_CONTENT_CEILING:
                content, _content_type, _filename = AttachmentsService.get_content(
                    ctx, payload.attachment_ulid
                )
                result["content_base64"] = base64.b64encode(content).decode("ascii")
            else:
                result["content_omitted"] = True
            return result
        except Exception as e:
            return error_response(e)
