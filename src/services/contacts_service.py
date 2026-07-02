"""Contacts service. Core mutation: log a contact event."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ..models import (
    AuditAction,
    ContactChannel,
    ContactLogRecord,
    FirmRecord,
    InitiatedBy,
    OutreachStage,
    PartnerRecord,
    RelationshipState,
)
from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


@dataclass
class LogContactResponse:
    contact: ContactLogRecord
    partner: PartnerRecord
    firm: FirmRecord
    state_advanced: bool
    new_state: RelationshipState | None
    stage_advanced: bool = False
    new_stage: OutreachStage | None = None


def _record_to_dict(record: Any) -> dict[str, Any]:
    d = record.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _contact_search_text(contact: ContactLogRecord, partner_name: str) -> tuple[str, str]:
    secondary = " ".join(filter(None, [
        partner_name,
        contact.summary,
        contact.value_given,
        contact.value_received,
        contact.follow_up,
    ]))
    return f"{partner_name} — {contact.contact_date.isoformat()}", secondary


def _evaluate_state_advance(
    *,
    partner_state: RelationshipState,
    firm_state: RelationshipState,
    given_this_contact: bool,
    received_this_contact: bool,
    total_given: int,
    total_received: int,
    substantive_count: int,
) -> RelationshipState | None:
    """Rule 1: state advancement on contact.

    - cold → warming if value exchanged AND firm state is cold.
    - warming → warm if substantive_count ≥ 3 with reciprocity across history.
    """
    if partner_state == RelationshipState.cold and firm_state == RelationshipState.cold:
        if given_this_contact or received_this_contact:
            return RelationshipState.warming
    if partner_state == RelationshipState.warming:
        if substantive_count >= 3 and total_given >= 1 and total_received >= 1:
            return RelationshipState.warm
    if partner_state == RelationshipState.dormant:
        return RelationshipState.warming
    return None


_MET_CHANNELS = {ContactChannel.call, ContactChannel.coffee, ContactChannel.event}

_STAGE_ORDER = [
    OutreachStage.researched,
    OutreachStage.drafted,
    OutreachStage.sent,
    OutreachStage.replied,
    OutreachStage.met,
]


def _evaluate_stage_advance(
    *,
    stage: OutreachStage,
    channel: ContactChannel,
    initiated_by: InitiatedBy,
) -> OutreachStage | None:
    """Rule 2: outreach-stage advancement on contact.

    - real-time channel (call/coffee/event) → met
    - inbound contact → replied
    - outbound contact → sent
    Only ever moves forward within researched→drafted→sent→replied→met;
    ongoing/paused/dropped are never touched.
    """
    if stage not in _STAGE_ORDER:
        return None
    if channel in _MET_CHANNELS:
        target = OutreachStage.met
    elif initiated_by == InitiatedBy.them:
        target = OutreachStage.replied
    else:
        target = OutreachStage.sent
    if _STAGE_ORDER.index(target) > _STAGE_ORDER.index(stage):
        return target
    return None


def _is_substantive(contact: ContactLogRecord) -> bool:
    return any([
        contact.value_given,
        contact.value_received,
        (contact.summary and len(contact.summary.strip()) > 0),
    ])


class ContactsService:

    @staticmethod
    def log(
        ctx: ServiceContext,
        *,
        firm_name: str,
        partner_name: str,
        contact_date: date,
        channel: ContactChannel,
        initiated_by: InitiatedBy,
        value_given: str | None = None,
        value_received: str | None = None,
        summary: str | None = None,
        follow_up: str | None = None,
        engagement_ulid: str | None = None,
        advance_state: bool = True,
        advance_stage: bool = True,
        next_touch_date: date | None = None,
        next_touch_topic: str | None = None,
    ) -> LogContactResponse:
        with transaction(ctx.conn):
            firm = firms_repo.get_firm_by_name(ctx.conn, firm_name)
            if firm is None:
                raise NotFoundError(f"firm not found: {firm_name}")
            partner = partners_repo.get_partner_by_name(ctx.conn, firm.id, partner_name)
            if partner is None:
                raise NotFoundError(f"partner not found: {firm_name} / {partner_name}")

            # v1.2: optionally link the contact to the engagement it concerned.
            engagement_id: int | None = None
            if engagement_ulid:
                from ..repository import engagements as engagements_repo

                engagement = engagements_repo.get_engagement_by_ulid(ctx.conn, engagement_ulid)
                if engagement is None:
                    raise NotFoundError(f"engagement not found: {engagement_ulid}")
                engagement_id = engagement.id

            contact = contacts_repo.insert_contact(
                ctx.conn,
                partner_id=partner.id,
                contact_date=contact_date,
                channel=channel,
                initiated_by=initiated_by,
                summary=summary,
                value_given=value_given,
                value_received=value_received,
                follow_up=follow_up,
                engagement_id=engagement_id,
            )

            partners_repo.update_last_contact_date(ctx.conn, partner.id, contact_date)

            # Inline next-touch scheduling: one log call closes the loop.
            touch_fields: dict[str, Any] = {}
            if next_touch_date is not None:
                touch_fields["next_touch_date"] = next_touch_date
            if next_touch_topic is not None:
                touch_fields["next_touch_topic"] = next_touch_topic
            if touch_fields:
                partners_repo.update_partner_fields(ctx.conn, partner.id, touch_fields)

            new_stage: OutreachStage | None = None
            if advance_stage:
                target_stage = _evaluate_stage_advance(
                    stage=partner.outreach_stage,
                    channel=channel,
                    initiated_by=initiated_by,
                )
                if target_stage is not None:
                    from .outreach_service import _set_stage_inline

                    _set_stage_inline(ctx, partner, target_stage)
                    new_stage = target_stage

            new_state: RelationshipState | None = None
            if advance_state:
                total_given, total_received = contacts_repo.count_value_given_received(
                    ctx.conn, partner.id
                )
                history = contacts_repo.list_contacts_by_partner(ctx.conn, partner.id)
                substantive_count = sum(1 for c in history if _is_substantive(c))
                new_state = _evaluate_state_advance(
                    partner_state=partner.relationship_state,
                    firm_state=firm.relationship_state,
                    given_this_contact=bool(value_given),
                    received_this_contact=bool(value_received),
                    total_given=total_given,
                    total_received=total_received,
                    substantive_count=substantive_count,
                )
                if new_state is not None:
                    partners_repo.update_partner_fields(
                        ctx.conn, partner.id, {"relationship_state": new_state}
                    )

            if summary or value_given or value_received:
                primary, secondary = _contact_search_text(contact, partner.name)
                search_repo.upsert_search_row(
                    ctx.conn,
                    entity_type="contact",
                    entity_ulid=contact.ulid,
                    primary_text=primary,
                    secondary_text=secondary,
                )

            refreshed = partners_repo.get_partner_by_id(ctx.conn, partner.id) or partner

            AuditService.record(
                ctx,
                action=AuditAction.log_contact,
                entity_type="contact",
                entity_id=contact.id,
                entity_ulid=contact.ulid,
                before=None,
                after={
                    "contact": _record_to_dict(contact),
                    "partner_ulid": partner.ulid,
                    "state_advanced": new_state is not None,
                    "new_state": new_state.value if new_state else None,
                    "stage_advanced": new_stage is not None,
                    "new_stage": new_stage.value if new_stage else None,
                    "next_touch_date": (
                        next_touch_date.isoformat() if next_touch_date else None
                    ),
                    "next_touch_topic": next_touch_topic,
                },
            )
            return LogContactResponse(
                contact=contact,
                partner=refreshed,
                firm=firm,
                state_advanced=new_state is not None,
                new_state=new_state,
                stage_advanced=new_stage is not None,
                new_stage=new_stage,
            )

    @staticmethod
    def list_by_partner(
        ctx: ServiceContext, partner_ulid: str, *, limit: int = 20
    ) -> list[ContactLogRecord]:
        partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
        if partner is None:
            raise NotFoundError(f"partner not found: {partner_ulid}")
        return contacts_repo.list_contacts_by_partner(ctx.conn, partner.id, limit=limit)

    @staticmethod
    def list_by_firm(ctx: ServiceContext, firm_ulid: str) -> list[ContactLogRecord]:
        firm = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
        if firm is None:
            raise NotFoundError(f"firm not found: {firm_ulid}")
        return contacts_repo.list_contacts_by_firm(ctx.conn, firm.id)

    @staticmethod
    def list_recent(ctx: ServiceContext, *, limit: int = 20) -> list[ContactLogRecord]:
        return contacts_repo.list_recent_contacts(ctx.conn, limit=limit)
