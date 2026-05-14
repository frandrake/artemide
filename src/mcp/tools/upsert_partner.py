"""Upsert a partner by (firm_ulid, name)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import UpsertPartnerInput
from ...repository import firms as firms_repo
from ...services.exceptions import NotFoundError
from ...services.partners_service import PartnersService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def upsert_partner(payload: UpsertPartnerInput) -> dict:
    """Create or update a partner at the given firm."""
    with tool_session("upsert_partner") as (conn, ctx):
        try:
            firm = firms_repo.get_firm_by_ulid(conn, payload.firm_ulid)
            if firm is None:
                raise NotFoundError(f"firm not found: {payload.firm_ulid}")
            fields = payload.model_dump(
                exclude={"firm_ulid", "name"}, exclude_none=True
            )
            partner = PartnersService.upsert(ctx, firm.name, payload.name, **fields)
            return {"ok": True, "partner": to_response(partner)}
        except Exception as e:
            return error_response(e)
