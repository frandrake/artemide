"""Log a contact event with a partner."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import LogContactInput
from ...repository import firms as firms_repo
from ...repository import partners as partners_repo
from ...services.contacts_service import ContactsService
from ...services.exceptions import NotFoundError
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def log_contact(payload: LogContactInput) -> dict:
    """Record a contact event for an existing partner."""
    with tool_session("log_contact") as (conn, ctx):
        try:
            partner = partners_repo.get_partner_by_ulid(conn, payload.partner_ulid)
            if partner is None:
                raise NotFoundError(f"partner not found: {payload.partner_ulid}")
            firm = firms_repo.get_firm_by_id(conn, partner.firm_id)
            assert firm is not None
            resp = ContactsService.log(
                ctx,
                firm_name=firm.name,
                partner_name=partner.name,
                contact_date=payload.contact_date,
                channel=payload.channel,
                initiated_by=payload.initiated_by,
                summary=payload.summary,
                value_given=payload.value_given,
                value_received=payload.value_received,
                follow_up=payload.follow_up,
                advance_state=payload.advance_state,
                advance_stage=payload.advance_stage,
                next_touch_date=payload.next_touch_date,
                next_touch_topic=payload.next_touch_topic,
            )
            return {
                "ok": True,
                "contact": to_response(resp.contact),
                "partner_ulid": resp.partner.ulid,
                "firm_ulid": resp.firm.ulid,
                "state_advanced": resp.state_advanced,
                "new_state": resp.new_state.value if resp.new_state else None,
                "stage_advanced": resp.stage_advanced,
                "new_stage": resp.new_stage.value if resp.new_stage else None,
                "next_touch_date": (
                    resp.partner.next_touch_date.isoformat()
                    if resp.partner.next_touch_date else None
                ),
            }
        except Exception as e:
            return error_response(e)
