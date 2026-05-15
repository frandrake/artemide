"""Create a reusable outreach template."""
from __future__ import annotations

from ...models import TemplateCreateInput
from ...services.templates_service import TemplatesService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def create_template(payload: TemplateCreateInput) -> dict:
    """Create a reusable outreach template with Mustache-lite variables."""
    with tool_session("create_template") as (_, ctx):
        try:
            rec = TemplatesService.create(ctx, payload)
            return {"ok": True, "template": rec.model_dump(mode="json")}
        except Exception as e:
            return error_response(e)
