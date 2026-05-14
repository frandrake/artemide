"""Fetch a partner's profile plus recent contacts."""
from __future__ import annotations

from ...api._serde import to_response, to_response_list
from ...models import GetPartnerStateInput
from ...services.contacts_service import ContactsService
from ...services.partners_service import PartnersService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def get_partner_state(payload: GetPartnerStateInput) -> dict:
    """Return the partner record, its firm, and recent contact history."""
    with tool_session("get_partner_state") as (conn, ctx):
        try:
            pwf = PartnersService.get_by_ulid(ctx, payload.partner_ulid)
            history = ContactsService.list_by_partner(
                ctx, payload.partner_ulid, limit=20
            )
            return {
                "ok": True,
                "partner": to_response(pwf.partner),
                "firm": to_response(pwf.firm),
                "contacts": to_response_list(history),
            }
        except Exception as e:
            return error_response(e)
