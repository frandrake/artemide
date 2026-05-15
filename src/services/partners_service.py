"""Partners service. Upsert by (firm, name), follow-ups, soft delete."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..models import AuditAction, FirmRecord, PartnerRecord, PartnerUpdateInput, RelationshipState
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, InvalidStateTransitionError, NotFoundError, ValidationError


@dataclass
class PartnerWithFirm:
    partner: PartnerRecord
    firm: FirmRecord


def _record_to_dict(partner: PartnerRecord) -> dict[str, Any]:
    d = partner.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _partner_search_text(partner: PartnerRecord, firm_name: str) -> tuple[str, str]:
    secondary_parts = [
        firm_name,
        partner.title,
        partner.practice,
        partner.seniority,
        partner.notes_summary,
        partner.practice_focus,
        partner.warm_intro_angle,
    ]
    return partner.name, " ".join(p for p in secondary_parts if p)


_ALLOWED_UPSERT_FIELDS = {
    "title", "practice", "seniority", "email", "linkedin_url",
    "relationship_state", "next_touch_date", "next_touch_topic",
    "notes_summary",
}


class PartnersService:

    @staticmethod
    def list_by_firm(ctx: ServiceContext, firm_ulid: str) -> list[PartnerRecord]:
        firm = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
        if firm is None:
            raise NotFoundError(f"firm not found: {firm_ulid}")
        return partners_repo.list_partners_by_firm(ctx.conn, firm.id)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> PartnerWithFirm:
        partner = partners_repo.get_partner_by_ulid(ctx.conn, ulid)
        if partner is None:
            raise NotFoundError(f"partner not found: {ulid}")
        firm = firms_repo.get_firm_by_id(ctx.conn, partner.firm_id)
        assert firm is not None
        return PartnerWithFirm(partner=partner, firm=firm)

    @staticmethod
    def get_by_name(
        ctx: ServiceContext, firm_name: str, partner_name: str
    ) -> PartnerWithFirm:
        firm = firms_repo.get_firm_by_name(ctx.conn, firm_name)
        if firm is None:
            raise NotFoundError(f"firm not found: {firm_name}")
        partner = partners_repo.get_partner_by_name(ctx.conn, firm.id, partner_name)
        if partner is None:
            raise NotFoundError(f"partner not found: {firm_name} / {partner_name}")
        return PartnerWithFirm(partner=partner, firm=firm)

    @staticmethod
    def upsert(
        ctx: ServiceContext,
        firm_name: str,
        name: str,
        **fields: Any,
    ) -> PartnerRecord:
        with transaction(ctx.conn):
            firm = firms_repo.get_firm_by_name(ctx.conn, firm_name)
            if firm is None:
                raise NotFoundError(f"firm not found: {firm_name}")

            clean = {k: v for k, v in fields.items() if k in _ALLOWED_UPSERT_FIELDS and v is not None}
            existing = partners_repo.get_partner_by_name(ctx.conn, firm.id, name)

            if existing is None:
                partner = partners_repo.insert_partner(
                    ctx.conn,
                    firm_id=firm.id,
                    name=name,
                    title=clean.get("title"),
                    practice=clean.get("practice"),
                    seniority=clean.get("seniority"),
                    email=clean.get("email"),
                    linkedin_url=clean.get("linkedin_url"),
                    relationship_state=clean.get("relationship_state", RelationshipState.cold),
                    next_touch_date=clean.get("next_touch_date"),
                    next_touch_topic=clean.get("next_touch_topic"),
                    notes_summary=clean.get("notes_summary"),
                )
                primary, secondary = _partner_search_text(partner, firm.name)
                search_repo.upsert_search_row(
                    ctx.conn,
                    entity_type="partner",
                    entity_ulid=partner.ulid,
                    primary_text=primary,
                    secondary_text=secondary,
                )
                AuditService.record(
                    ctx,
                    action=AuditAction.create,
                    entity_type="partner",
                    entity_id=partner.id,
                    entity_ulid=partner.ulid,
                    before=None,
                    after=_record_to_dict(partner),
                )
                return partner

            before = _record_to_dict(existing)
            updated = partners_repo.update_partner_fields(ctx.conn, existing.id, clean) or existing
            primary, secondary = _partner_search_text(updated, firm.name)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="partner",
                entity_ulid=updated.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="partner",
                entity_id=updated.id,
                entity_ulid=updated.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_planned_touch(
        ctx: ServiceContext, ulid: str, next_date: date | None, topic: str | None
    ) -> PartnerRecord:
        with transaction(ctx.conn):
            pwf = PartnersService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(pwf.partner)
            updated = partners_repo.update_partner_fields(
                ctx.conn,
                pwf.partner.id,
                {"next_touch_date": next_date, "next_touch_topic": topic},
            ) or pwf.partner
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="partner",
                entity_id=updated.id,
                entity_ulid=updated.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_follow_ups(
        ctx: ServiceContext, ulid: str, follow_ups: list[str]
    ) -> PartnerRecord:
        with transaction(ctx.conn):
            pwf = PartnersService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(pwf.partner)
            serialised = json.dumps([str(f) for f in follow_ups]) if follow_ups else None
            updated = partners_repo.update_partner_fields(
                ctx.conn,
                pwf.partner.id,
                {"follow_ups_outstanding": serialised},
            ) or pwf.partner
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="partner",
                entity_id=updated.id,
                entity_ulid=updated.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: PartnerUpdateInput) -> PartnerRecord:
        _FIELD_MAP = {
            "first_contact_date": "last_contact_date",
            "next_planned_touch_date": "next_touch_date",
            "next_planned_topic": "next_touch_topic",
        }
        _ALLOWED_COLUMNS = {
            "name", "practice", "seniority", "location", "introduced_via",
            "last_contact_date", "next_touch_date", "next_touch_topic",
            "follow_ups_outstanding",
            "practice_focus", "strategic_relevance", "warm_intro_angle",
            "thought_leadership", "prior_career", "ned_gateway",
            "outreach_stage",
        }
        with transaction(ctx.conn):
            pwf = PartnersService.get_by_ulid(ctx, ulid)
            partner = pwf.partner
            if partner.deleted_at is not None:
                raise NotFoundError(f"partner not found: {ulid}")
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            # Rule P3: date ordering using merged new+existing values.
            fcd = raw.get("first_contact_date", partner.last_contact_date)
            npt = raw.get("next_planned_touch_date", partner.next_touch_date)
            if fcd and npt and npt <= fcd:
                raise ValidationError("next_planned_touch_date must be after first_contact_date")
            # Name collision check.
            new_name = raw.get("name")
            if new_name is not None and new_name != partner.name:
                collision = partners_repo.get_partner_by_name(ctx.conn, partner.firm_id, new_name)
                if collision is not None and collision.deleted_at is None:
                    raise ConflictError(f"a partner named '{new_name}' already exists at this firm")
            # Map spec field names → DB column names, filter to allowed set.
            mapped: dict = {}
            for k, v in raw.items():
                db_key = _FIELD_MAP.get(k, k)
                if db_key in _ALLOWED_COLUMNS:
                    mapped[db_key] = v
            # Serialise compound types.
            if "follow_ups_outstanding" in mapped:
                mapped["follow_ups_outstanding"] = json.dumps(mapped["follow_ups_outstanding"])
            fields = {k: str(v) if isinstance(v, date) else v for k, v in mapped.items()}
            before = _record_to_dict(partner)
            updated = partners_repo.update_partner_fields(ctx.conn, partner.id, fields)
            assert updated is not None
            primary, secondary = _partner_search_text(updated, pwf.firm.name)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="partner",
                entity_ulid=updated.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="partner",
                entity_id=partner.id,
                entity_ulid=partner.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        with transaction(ctx.conn):
            pwf = PartnersService.get_by_ulid(ctx, ulid)
            if pwf.partner.deleted_at is not None:
                raise ConflictError("partner already deleted")
            before = _record_to_dict(pwf.partner)
            partners_repo.soft_delete_partner(ctx.conn, pwf.partner.id)
            search_repo.delete_search_row(
                ctx.conn, entity_type="partner", entity_ulid=pwf.partner.ulid
            )
            AuditService.record(
                ctx,
                action=AuditAction.delete,
                entity_type="partner",
                entity_id=pwf.partner.id,
                entity_ulid=pwf.partner.ulid,
                before=before,
                after=None,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> PartnerRecord:
        with transaction(ctx.conn):
            partner = partners_repo.get_partner_by_ulid(ctx.conn, ulid)
            if partner is None:
                raise NotFoundError(f"partner not found: {ulid}")
            if partner.deleted_at is None:
                return partner
            # Rule P5: parent firm must be active.
            firm = firms_repo.get_firm_by_id(ctx.conn, partner.firm_id)
            assert firm is not None
            if firm.deleted_at is not None:
                raise InvalidStateTransitionError("restore the parent firm before restoring this partner")
            partners_repo.restore_partner(ctx.conn, partner.id)
            restored = partners_repo.get_partner_by_ulid(ctx.conn, ulid)
            assert restored is not None
            primary, secondary = _partner_search_text(restored, firm.name)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="partner",
                entity_ulid=restored.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.restore,
                entity_type="partner",
                entity_id=restored.id,
                entity_ulid=restored.ulid,
                before=None,
                after=_record_to_dict(restored),
            )
            return restored
