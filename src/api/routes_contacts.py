"""/api/v1/contacts routes."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..models import ContactChannel, InitiatedBy
from ..repository import contacts as contacts_repo
from ..services import ServiceContext
from ..services.contacts_service import ContactsService
from ..services.exceptions import NotFoundError
from ._serde import to_response, to_response_list
from .deps import (
    get_context,
    get_db,
    idempotency_key_header,
    lookup_idempotent_response,
    store_idempotent_response,
)

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


class ContactLogInput(BaseModel):
    firm_name: str
    partner_name: str
    contact_date: date
    channel: ContactChannel
    initiated_by: InitiatedBy
    summary: str | None = None
    value_given: str | None = None
    value_received: str | None = None
    follow_up: str | None = None
    advance_state: bool = True
    advance_stage: bool = True
    next_touch_date: date | None = None
    next_touch_topic: str | None = None


@router.get("")
def list_contacts(
    partner_ulid: str | None = Query(default=None),
    firm_ulid: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    ctx: ServiceContext = Depends(get_context),
):
    if partner_ulid:
        return to_response_list(
            ContactsService.list_by_partner(ctx, partner_ulid, limit=limit)
        )
    if firm_ulid:
        return to_response_list(ContactsService.list_by_firm(ctx, firm_ulid))
    return to_response_list(ContactsService.list_recent(ctx, limit=limit))


@router.post("")
def log_contact(
    body: ContactLogInput,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: ServiceContext = Depends(get_context),
    idempotency_key: str | None = Depends(idempotency_key_header),
):
    cached = lookup_idempotent_response(conn, idempotency_key)
    if cached is not None:
        return cached
    resp = ContactsService.log(
        ctx,
        firm_name=body.firm_name,
        partner_name=body.partner_name,
        contact_date=body.contact_date,
        channel=body.channel,
        initiated_by=body.initiated_by,
        summary=body.summary,
        value_given=body.value_given,
        value_received=body.value_received,
        follow_up=body.follow_up,
        advance_state=body.advance_state,
        advance_stage=body.advance_stage,
        next_touch_date=body.next_touch_date,
        next_touch_topic=body.next_touch_topic,
    )
    payload = {
        "contact": to_response(resp.contact),
        "partner_ulid": resp.partner.ulid,
        "firm_ulid": resp.firm.ulid,
        "state_advanced": resp.state_advanced,
        "new_state": resp.new_state.value if resp.new_state else None,
        "stage_advanced": resp.stage_advanced,
        "new_stage": resp.new_stage.value if resp.new_stage else None,
    }
    store_idempotent_response(conn, idempotency_key, payload, status_code=200)
    return payload


@router.get("/{ulid}")
def get_contact(ulid: str, ctx: ServiceContext = Depends(get_context)):
    contact = contacts_repo.get_contact_by_ulid(ctx.conn, ulid)
    if contact is None:
        raise NotFoundError(f"contact not found: {ulid}")
    return to_response(contact)
