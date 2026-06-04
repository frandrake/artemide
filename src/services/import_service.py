"""Import service. Idempotent markdown ledger ingest."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..models import (
    AuditAction,
    ContactChannel,
    FirmTier,
    InitiatedBy,
    RelationshipState,
)
from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import ValidationError
from .firms_service import FirmsService
from .partners_service import PartnersService


@dataclass
class ImportSummary:
    firms_created: int = 0
    firms_updated: int = 0
    partners_created: int = 0
    partners_updated: int = 0
    contacts_imported: int = 0
    contacts_skipped: int = 0
    errors: list[str] = field(default_factory=list)


_CONTACT_LINE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}) \| ([a-z_]+) \| ([a-z_]+)\s*$"
)
_KV_LINE = re.compile(r"^\s*-\s+\*\*([A-Za-z-]+):\*\*\s+(.+?)\s*$")


@dataclass
class _ParsedFirm:
    name: str
    tier: FirmTier
    region: str | None = None
    relationship_state: RelationshipState | None = None
    primary_focus: str | None = None
    notes_summary: str | None = None
    partners: list["_ParsedPartner"] = field(default_factory=list)


@dataclass
class _ParsedPartner:
    name: str
    title: str | None = None
    practice: str | None = None
    seniority: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relationship_state: RelationshipState | None = None
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    notes_summary: str | None = None
    contacts: list["_ParsedContact"] = field(default_factory=list)


@dataclass
class _ParsedContact:
    contact_date: date
    channel: ContactChannel
    initiated_by: InitiatedBy
    summary: str | None = None
    value_given: str | None = None
    value_received: str | None = None
    follow_up: str | None = None


_FIRM_KV_MAP = {
    "region": "region",
    "state": "relationship_state",
    "focus": "primary_focus",
    "notes": "notes_summary",
}
_PARTNER_KV_MAP = {
    "title": "title",
    "practice": "practice",
    "seniority": "seniority",
    "email": "email",
    "linkedin": "linkedin_url",
    "state": "relationship_state",
    "next-touch-date": "next_touch_date",
    "next-touch-topic": "next_touch_topic",
    "notes": "notes_summary",
}
_CONTACT_KV_MAP = {
    "summary": "summary",
    "value-given": "value_given",
    "value-received": "value_received",
    "follow-up": "follow_up",
}


def _parse(content: str) -> list[_ParsedFirm]:
    firms: list[_ParsedFirm] = []
    current_tier: FirmTier | None = None
    current_firm: _ParsedFirm | None = None
    current_partner: _ParsedPartner | None = None
    current_contact: _ParsedContact | None = None
    in_contacts_section = False

    for raw in content.splitlines():
        line = raw.rstrip()
        if line.startswith("## Tier:"):
            current_tier = FirmTier(line.split(":", 1)[1].strip())
            current_firm = current_partner = current_contact = None
            in_contacts_section = False
            continue
        if line.startswith("### Firm:"):
            name = line.split(":", 1)[1].strip()
            tier = current_tier or FirmTier.specialist
            current_firm = _ParsedFirm(name=name, tier=tier)
            firms.append(current_firm)
            current_partner = current_contact = None
            in_contacts_section = False
            continue
        if line.startswith("#### Partner:") and current_firm is not None:
            name = line.split(":", 1)[1].strip()
            current_partner = _ParsedPartner(name=name)
            current_firm.partners.append(current_partner)
            current_contact = None
            in_contacts_section = False
            continue
        if line.startswith("##### Contacts"):
            in_contacts_section = True
            current_contact = None
            continue

        cm = _CONTACT_LINE.match(line)
        if cm and current_partner is not None and in_contacts_section:
            d = date.fromisoformat(cm.group(1))
            current_contact = _ParsedContact(
                contact_date=d,
                channel=ContactChannel(cm.group(2)),
                initiated_by=InitiatedBy(cm.group(3)),
            )
            current_partner.contacts.append(current_contact)
            continue

        kv = _KV_LINE.match(line)
        if kv:
            key = kv.group(1).strip().lower()
            value = kv.group(2).strip()
            if current_contact is not None and key in _CONTACT_KV_MAP:
                setattr(current_contact, _CONTACT_KV_MAP[key], value)
            elif current_partner is not None and not in_contacts_section and key in _PARTNER_KV_MAP:
                field_name = _PARTNER_KV_MAP[key]
                _set_partner_field(current_partner, field_name, value)
            elif current_firm is not None and current_partner is None and key in _FIRM_KV_MAP:
                field_name = _FIRM_KV_MAP[key]
                _set_firm_field(current_firm, field_name, value)
            continue
    return firms


def _set_firm_field(firm: _ParsedFirm, field_name: str, value: str) -> None:
    if field_name == "relationship_state":
        firm.relationship_state = RelationshipState(value)
    else:
        setattr(firm, field_name, value)


def _set_partner_field(partner: _ParsedPartner, field_name: str, value: str) -> None:
    if field_name == "relationship_state":
        partner.relationship_state = RelationshipState(value)
    elif field_name == "next_touch_date":
        partner.next_touch_date = date.fromisoformat(value)
    else:
        setattr(partner, field_name, value)


def _firm_fields_for_update(parsed: _ParsedFirm) -> dict:
    out = {}
    for attr in ("region", "primary_focus", "notes_summary"):
        v = getattr(parsed, attr)
        if v is not None:
            out[attr] = v
    if parsed.relationship_state is not None:
        out["relationship_state"] = parsed.relationship_state
    return out


def _partner_upsert_kwargs(parsed: _ParsedPartner) -> dict:
    out = {}
    for attr in ("title", "practice", "seniority", "email", "linkedin_url",
                 "next_touch_topic", "notes_summary", "next_touch_date"):
        v = getattr(parsed, attr)
        if v is not None:
            out[attr] = v
    if parsed.relationship_state is not None:
        out["relationship_state"] = parsed.relationship_state
    return out


class ImportService:

    @staticmethod
    def import_markdown(
        ctx: ServiceContext,
        content: str,
        *,
        overwrite_existing: bool = False,
    ) -> ImportSummary:
        summary = ImportSummary()
        # Parse fully before opening the write transaction: parsing is pure, so a
        # malformed ledger fails fast with a structured error and writes nothing
        # (no partial import, and the error reaches the caller instead of a 500).
        try:
            parsed_firms = _parse(content)
        except Exception as e:
            raise ValidationError(f"could not parse ledger: {e}") from e

        with transaction(ctx.conn):
            for pfirm in parsed_firms:
                existing_firm = firms_repo.get_firm_by_name(ctx.conn, pfirm.name)
                if existing_firm is None:
                    firm = FirmsService._create_internal(
                        ctx,
                        name=pfirm.name,
                        tier=pfirm.tier,
                        region=pfirm.region,
                        relationship_state=pfirm.relationship_state or RelationshipState.cold,
                        primary_focus=pfirm.primary_focus,
                        notes_summary=pfirm.notes_summary,
                    )
                    summary.firms_created += 1
                else:
                    firm = existing_firm
                    resurrected = False
                    if firm.deleted_at is not None:
                        # Re-import resurrects a soft-deleted firm rather than
                        # attaching new partners/contacts to a tombstone.
                        firm = FirmsService._restore_internal(ctx, firm)
                        resurrected = True
                    update_fields = _firm_fields_for_update(pfirm)
                    if overwrite_existing and update_fields:
                        FirmsService._update_internal(ctx, firm=firm, fields=update_fields)
                        summary.firms_updated += 1
                    elif resurrected:
                        summary.firms_updated += 1

                for pp in pfirm.partners:
                    existing_partner = partners_repo.get_partner_by_name(
                        ctx.conn, firm.id, pp.name
                    )
                    if existing_partner is None:
                        PartnersService.upsert(
                            ctx,
                            firm_name=firm.name,
                            name=pp.name,
                            **_partner_upsert_kwargs(pp),
                        )
                        summary.partners_created += 1
                    else:
                        if existing_partner.deleted_at is not None:
                            # Resurrect a soft-deleted partner under the (now
                            # active) firm rather than logging onto a tombstone.
                            PartnersService._restore_internal(ctx, existing_partner, firm)
                            if not overwrite_existing:
                                summary.partners_updated += 1
                        if overwrite_existing:
                            PartnersService.upsert(
                                ctx,
                                firm_name=firm.name,
                                name=pp.name,
                                **_partner_upsert_kwargs(pp),
                            )
                            summary.partners_updated += 1

                    partner_row = partners_repo.get_partner_by_name(ctx.conn, firm.id, pp.name)
                    assert partner_row is not None

                    for c in pp.contacts:
                        if contacts_repo.is_duplicate_contact(
                            ctx.conn, partner_row.id, c.contact_date, c.channel, c.initiated_by
                        ):
                            summary.contacts_skipped += 1
                            continue
                        contact = contacts_repo.insert_contact(
                            ctx.conn,
                            partner_id=partner_row.id,
                            contact_date=c.contact_date,
                            channel=c.channel,
                            initiated_by=c.initiated_by,
                            summary=c.summary,
                            value_given=c.value_given,
                            value_received=c.value_received,
                            follow_up=c.follow_up,
                        )
                        partners_repo.update_last_contact_date(
                            ctx.conn, partner_row.id, c.contact_date
                        )
                        summary.contacts_imported += 1
                        AuditService.record(
                            ctx,
                            action=AuditAction.import_,
                            entity_type="contact",
                            entity_id=contact.id,
                            entity_ulid=contact.ulid,
                            before=None,
                            after={
                                "contact_date": c.contact_date.isoformat(),
                                "channel": c.channel.value,
                                "partner": pp.name,
                                "firm": firm.name,
                            },
                        )
            AuditService.record(
                ctx,
                action=AuditAction.import_,
                entity_type="ledger",
                entity_ulid=None,
                before=None,
                after={
                    "firms_created": summary.firms_created,
                    "firms_updated": summary.firms_updated,
                    "partners_created": summary.partners_created,
                    "partners_updated": summary.partners_updated,
                    "contacts_imported": summary.contacts_imported,
                    "contacts_skipped": summary.contacts_skipped,
                },
            )
        return summary
