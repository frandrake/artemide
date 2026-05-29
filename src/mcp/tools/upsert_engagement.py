"""Create or update an engagement (a role in motion)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import UpsertEngagementInput
from ...repository import orgs as orgs_repo
from ...services.engagements_service import EngagementsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def upsert_engagement(payload: UpsertEngagementInput) -> dict:
    """Create or update an engagement at an organisation (matched by ulid or org+role)."""
    with tool_session("upsert_engagement") as (conn, ctx):
        try:
            e = EngagementsService.upsert(ctx, payload)
            org = orgs_repo.get_org_by_id(conn, e.org_id)
            out = to_response(e, extra_exclude={"org_id", "source_partner_id"})
            out["org_ulid"] = org.ulid if org else None
            return {"ok": True, "engagement": out}
        except Exception as e:
            return error_response(e)
