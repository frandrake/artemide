"""Create or update an organisation of interest."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import UpsertOrgInput
from ...services.orgs_service import OrgsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def upsert_org(payload: UpsertOrgInput) -> dict:
    """Create or update an organisation (matched by ulid or name)."""
    with tool_session("upsert_org") as (conn, ctx):
        try:
            org = OrgsService.upsert(ctx, payload)
            return {"ok": True, "org": to_response(org)}
        except Exception as e:
            return error_response(e)
