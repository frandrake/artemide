"""Render a template against a partner; returns subject + body + missing variables."""
from __future__ import annotations

from pydantic import BaseModel

from ...services.templates_service import TemplatesService
from .._common import error_response, tool_session
from ..registry import mcp


class RenderTemplateInput(BaseModel):
    template_ulid: str
    partner_ulid: str
    overrides: dict[str, str] | None = None


@mcp.tool
def render_template(payload: RenderTemplateInput) -> dict:
    """Render a template against a partner. Returns {subject, body, missing_variables, used_variables}."""
    with tool_session("render_template") as (_, ctx):
        try:
            out = TemplatesService.render(
                ctx,
                template_ulid=payload.template_ulid,
                partner_ulid=payload.partner_ulid,
                overrides=payload.overrides,
            )
            return {"ok": True, **out}
        except Exception as e:
            return error_response(e)
