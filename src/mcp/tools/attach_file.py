"""Upload a file (base64) and attach it to an entity."""
from __future__ import annotations

import base64
import binascii

from ...api._serde import to_response
from ...models import AttachFileInput
from ...services.attachments_service import AttachmentsService
from ...services.exceptions import ValidationError
from .._common import error_response, tool_session
from ..registry import mcp

# Decoded-bytes ceiling for the MCP path — tighter than the service's 25 MB.
_MCP_UPLOAD_CEILING = 4 * 1024 * 1024


@mcp.tool
def attach_file(payload: AttachFileInput) -> dict:
    """Decode base64 content and attach it; rejects payloads over 4 MB decoded."""
    with tool_session("attach_file") as (conn, ctx):
        try:
            try:
                content = base64.b64decode(payload.content_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValidationError("content_base64 is not valid base64")
            if len(content) > _MCP_UPLOAD_CEILING:
                raise ValidationError("file exceeds 4 MB MCP upload limit")
            rec = AttachmentsService.upload(
                ctx,
                entity_type=payload.entity_type,
                entity_ulid=payload.entity_ulid,
                kind=payload.kind,
                filename=payload.filename,
                content_type=payload.content_type,
                content=content,
            )
            return {"ok": True, "attachment": to_response(rec)}
        except Exception as e:
            return error_response(e)
