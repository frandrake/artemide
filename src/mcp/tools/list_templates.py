"""List reusable outreach templates."""
from __future__ import annotations

from pydantic import BaseModel

from ...services.templates_service import TemplatesService
from .._common import error_response, tool_session
from ..registry import mcp


class ListTemplatesInput(BaseModel):
    channel: str | None = None
    category: str | None = None


@mcp.tool
def list_templates(payload: ListTemplatesInput) -> dict:
    """List outreach templates filtered by channel or category."""
    with tool_session("list_templates") as (_, ctx):
        try:
            items = TemplatesService.list(
                ctx, channel=payload.channel, category=payload.category
            )
            return {"ok": True, "templates": [r.model_dump(mode="json") for r in items]}
        except Exception as e:
            return error_response(e)
