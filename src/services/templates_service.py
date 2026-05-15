"""Templates service. CRUD + rendering."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import (
    AuditAction,
    OutreachChannel,
    TemplateCreateInput,
    TemplateRecord,
    TemplateUpdateInput,
)
from ..repository import partners as partners_repo
from ..repository import firms as firms_repo
from ..repository import templates as templates_repo
from ..repository import search_index as search_repo
from ..repository import calendar as calendar_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError
from .template_render import build_context, render


def _record_to_dict(rec: TemplateRecord) -> dict[str, Any]:
    d = rec.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _search_text(rec: TemplateRecord) -> tuple[str, str]:
    secondary = " ".join(filter(None, [rec.category, rec.description, rec.channel.value]))
    return rec.name, secondary


class TemplatesService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        channel: OutreachChannel | str | None = None,
        category: str | None = None,
        include_deleted: bool = False,
    ) -> list[TemplateRecord]:
        ch_val = channel.value if hasattr(channel, "value") else channel
        return templates_repo.list_templates(
            ctx.conn,
            channel=ch_val,
            category=category,
            include_deleted=include_deleted,
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> TemplateRecord:
        rec = templates_repo.get_template_by_ulid(ctx.conn, ulid)
        if rec is None:
            raise NotFoundError(f"template not found: {ulid}")
        return rec

    @staticmethod
    def create(ctx: ServiceContext, data: TemplateCreateInput) -> TemplateRecord:
        with transaction(ctx.conn):
            existing = templates_repo.get_template_by_name(ctx.conn, data.name)
            if existing is not None and existing.deleted_at is None:
                raise ConflictError(f"template already exists: {data.name}")
            rec = templates_repo.insert_template(
                ctx.conn,
                name=data.name,
                channel=data.channel.value,
                body_template=data.body_template,
                subject_template=data.subject_template,
                category=data.category,
                description=data.description,
            )
            primary, secondary = _search_text(rec)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="template",
                entity_ulid=rec.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.template,
                entity_type="template",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=None,
                after=_record_to_dict(rec),
            )
            return rec

    @staticmethod
    def update(
        ctx: ServiceContext, ulid: str, data: TemplateUpdateInput
    ) -> TemplateRecord:
        with transaction(ctx.conn):
            rec = TemplatesService.get_by_ulid(ctx, ulid)
            if rec.deleted_at is not None:
                raise NotFoundError(f"template not found: {ulid}")
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            # Name-collision check
            if "name" in raw and raw["name"] != rec.name:
                other = templates_repo.get_template_by_name(ctx.conn, raw["name"])
                if other is not None and other.deleted_at is None:
                    raise ConflictError(f"template already exists: {raw['name']}")
            before = _record_to_dict(rec)
            updated = templates_repo.update_template_fields(ctx.conn, rec.id, raw)
            assert updated is not None
            primary, secondary = _search_text(updated)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="template",
                entity_ulid=updated.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.template,
                entity_type="template",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        with transaction(ctx.conn):
            rec = TemplatesService.get_by_ulid(ctx, ulid)
            if rec.deleted_at is not None:
                raise ConflictError("template already deleted")
            templates_repo.soft_delete_template(ctx.conn, rec.id)
            search_repo.delete_search_row(
                ctx.conn, entity_type="template", entity_ulid=rec.ulid
            )
            AuditService.record(
                ctx,
                action=AuditAction.template,
                entity_type="template",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=_record_to_dict(rec),
                after=None,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> TemplateRecord:
        with transaction(ctx.conn):
            rec = templates_repo.get_template_by_ulid(ctx.conn, ulid)
            if rec is None:
                raise NotFoundError(f"template not found: {ulid}")
            if rec.deleted_at is None:
                return rec
            templates_repo.restore_template(ctx.conn, rec.id)
            restored = templates_repo.get_template_by_ulid(ctx.conn, ulid)
            assert restored is not None
            primary, secondary = _search_text(restored)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="template",
                entity_ulid=restored.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.template,
                entity_type="template",
                entity_id=restored.id,
                entity_ulid=restored.ulid,
                before=None,
                after=_record_to_dict(restored),
            )
            return restored

    @staticmethod
    def render(
        ctx: ServiceContext,
        *,
        template_ulid: str,
        partner_ulid: str,
        overrides: dict[str, str] | None = None,
    ) -> dict:
        tmpl = TemplatesService.get_by_ulid(ctx, template_ulid)
        if tmpl.deleted_at is not None:
            raise NotFoundError(f"template not found: {template_ulid}")
        partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
        if partner is None:
            raise NotFoundError(f"partner not found: {partner_ulid}")
        firm = firms_repo.get_firm_by_id(ctx.conn, partner.firm_id)
        # Current quarter (used as soft context — may be None)
        today = date.today()
        q = ((today.month - 1) // 3) + 1
        quarter = calendar_repo.get_quarter_topic(ctx.conn, year=today.year, quarter=q)

        context = build_context(
            partner=partner, firm=firm, quarter=quarter, overrides=overrides
        )

        subject, subj_missing, subj_used = render(tmpl.subject_template or "", context)
        body, body_missing, body_used = render(tmpl.body_template, context)
        missing = list({*subj_missing, *body_missing})
        used = {**subj_used, **body_used}
        return {
            "subject": subject,
            "body": body,
            "missing_variables": missing,
            "used_variables": used,
        }
