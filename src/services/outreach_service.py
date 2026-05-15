"""Outreach service: draft → versions → atomic mark_sent.

mark_sent guarantees that one click produces:
  - exactly one new contact_log row
  - partner.last_contact_date updated
  - exactly one new outreach_message row (immutable)
  - draft.status flipped to 'sent', sent_message_id back-pointed
  - partner.outreach_stage advanced if currently drafted/researched
  - three audit_log rows (send, log_contact, optionally stage)

All in a single transaction. Any failure rolls everything back.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..models import (
    AuditAction,
    ContactChannel,
    DraftStatus,
    OutreachChannel,
    OutreachDraftCreateInput,
    OutreachDraftRecord,
    OutreachDraftUpdateInput,
    OutreachDraftVersionRecord,
    OutreachMessageRecord,
    OutreachSendInput,
    OutreachStage,
    PartnerRecord,
)
from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import outreach as outreach_repo
from ..repository import partners as partners_repo
from ..repository import templates as templates_repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError
from .templates_service import TemplatesService


# Mapping: OutreachChannel → ContactChannel (used when logging the implicit
# contact_log row that mark_sent creates).
_CHANNEL_MAP: dict[str, ContactChannel] = {
    "email": ContactChannel.email,
    "linkedin": ContactChannel.inmail,
    "message": ContactChannel.message,
    "other": ContactChannel.other,
}


def _draft_dict(d: OutreachDraftRecord) -> dict[str, Any]:
    out = d.model_dump(mode="json")
    return {k: v for k, v in out.items() if k not in ("created_at", "updated_at")}


def _summary_excerpt(body: str, max_len: int = 240) -> str:
    if len(body) <= max_len:
        return body.strip()
    return body[:max_len].rstrip() + "…"


class OutreachService:

    @staticmethod
    def list_drafts(
        ctx: ServiceContext,
        *,
        partner_ulid: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        limit: int = 50,
    ) -> list[OutreachDraftRecord]:
        partner_id: int | None = None
        if partner_ulid:
            p = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if p is None:
                raise NotFoundError(f"partner not found: {partner_ulid}")
            partner_id = p.id
        return outreach_repo.list_drafts(
            ctx.conn, status=status, channel=channel, partner_id=partner_id, limit=limit
        )

    @staticmethod
    def get_draft(ctx: ServiceContext, ulid: str) -> OutreachDraftRecord:
        rec = outreach_repo.get_draft_by_ulid(ctx.conn, ulid)
        if rec is None:
            raise NotFoundError(f"draft not found: {ulid}")
        return rec

    @staticmethod
    def list_versions(
        ctx: ServiceContext, ulid: str
    ) -> list[OutreachDraftVersionRecord]:
        draft = OutreachService.get_draft(ctx, ulid)
        return outreach_repo.list_draft_versions(ctx.conn, draft.id)

    @staticmethod
    def create_draft(
        ctx: ServiceContext, data: OutreachDraftCreateInput
    ) -> OutreachDraftRecord:
        with transaction(ctx.conn):
            partner = partners_repo.get_partner_by_ulid(ctx.conn, data.partner_ulid)
            if partner is None or partner.deleted_at is not None:
                raise NotFoundError(f"partner not found: {data.partner_ulid}")

            template_id: int | None = None
            subject = data.subject
            body = data.body or ""
            if data.template_ulid:
                tmpl = templates_repo.get_template_by_ulid(ctx.conn, data.template_ulid)
                if tmpl is None or tmpl.deleted_at is not None:
                    raise NotFoundError(f"template not found: {data.template_ulid}")
                template_id = tmpl.id
                # Server-render if body empty (lets the agent pass just a template_ulid).
                if not body.strip():
                    rendered = TemplatesService.render(
                        ctx,
                        template_ulid=data.template_ulid,
                        partner_ulid=data.partner_ulid,
                    )
                    body = rendered["body"]
                    if not subject:
                        subject = rendered["subject"] or None

            if not body.strip():
                raise ValidationError("body is required (either pass body or template_ulid)")

            rec = outreach_repo.insert_draft(
                ctx.conn,
                partner_id=partner.id,
                channel=data.channel.value,
                body=body,
                subject=subject,
                template_id=template_id,
                status=data.status.value,
            )
            outreach_repo.insert_draft_version(
                ctx.conn,
                draft_id=rec.id,
                version=1,
                subject=subject,
                body=body,
                author_actor=ctx.actor,
            )
            AuditService.record(
                ctx,
                action=AuditAction.draft,
                entity_type="outreach_draft",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=None,
                after=_draft_dict(rec),
            )
            # Stage auto-advance: researched → drafted
            if partner.outreach_stage == OutreachStage.researched:
                _set_stage_inline(ctx, partner, OutreachStage.drafted)
            return rec

    @staticmethod
    def update_draft(
        ctx: ServiceContext, ulid: str, data: OutreachDraftUpdateInput
    ) -> OutreachDraftRecord:
        with transaction(ctx.conn):
            rec = OutreachService.get_draft(ctx, ulid)
            if rec.status == DraftStatus.sent:
                raise ConflictError("draft already sent; immutable")
            if rec.status == DraftStatus.archived:
                raise ConflictError("draft is archived; restore not implemented yet")
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            if "status" in raw and raw["status"] == DraftStatus.sent:
                raise ValidationError("use the send endpoint to mark a draft sent")

            # Resolve template_ulid → template_id
            if "template_ulid" in raw:
                t_ulid = raw.pop("template_ulid")
                tmpl = templates_repo.get_template_by_ulid(ctx.conn, t_ulid)
                if tmpl is None:
                    raise NotFoundError(f"template not found: {t_ulid}")
                raw["template_id"] = tmpl.id

            content_changed = (
                ("body" in raw and raw["body"] != rec.body) or
                ("subject" in raw and raw["subject"] != rec.subject)
            )
            new_version = rec.version + 1 if content_changed else rec.version
            if content_changed:
                raw["version"] = new_version

            before = _draft_dict(rec)
            updated = outreach_repo.update_draft_fields(ctx.conn, rec.id, raw)
            assert updated is not None

            if content_changed:
                outreach_repo.insert_draft_version(
                    ctx.conn,
                    draft_id=rec.id,
                    version=new_version,
                    subject=updated.subject,
                    body=updated.body,
                    author_actor=ctx.actor,
                )

            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="outreach_draft",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=before,
                after=_draft_dict(updated),
            )
            return updated

    @staticmethod
    def archive_draft(ctx: ServiceContext, ulid: str) -> OutreachDraftRecord:
        with transaction(ctx.conn):
            rec = OutreachService.get_draft(ctx, ulid)
            if rec.status == DraftStatus.sent:
                raise ConflictError("sent drafts cannot be archived")
            before = _draft_dict(rec)
            outreach_repo.archive_draft(ctx.conn, rec.id)
            updated = outreach_repo.get_draft_by_id(ctx.conn, rec.id)
            assert updated is not None
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="outreach_draft",
                entity_id=rec.id,
                entity_ulid=rec.ulid,
                before=before,
                after=_draft_dict(updated),
            )
            return updated

    @staticmethod
    def mark_sent(ctx: ServiceContext, data: OutreachSendInput) -> dict:
        with transaction(ctx.conn):
            draft = OutreachService.get_draft(ctx, data.draft_ulid)
            if draft.status == DraftStatus.sent:
                raise ConflictError("draft already sent")
            if draft.status == DraftStatus.archived:
                raise ConflictError("cannot send an archived draft")

            # sent_at: default now; cap backdating at 7 days
            sent_at = data.sent_at or datetime.now()
            if sent_at.tzinfo is not None:
                sent_at = sent_at.astimezone(timezone.utc).replace(tzinfo=None)
            cap = datetime.now() - timedelta(days=7)
            if sent_at < cap:
                raise ValidationError("sent_at cannot be more than 7 days in the past")
            future_cap = datetime.now() + timedelta(minutes=5)
            if sent_at > future_cap:
                raise ValidationError("sent_at cannot be in the future")

            sent_via = (data.sent_via or draft.channel).value if hasattr(
                data.sent_via or draft.channel, "value"
            ) else (data.sent_via or draft.channel)

            partner = partners_repo.get_partner_by_id(ctx.conn, draft.partner_id)
            if partner is None or partner.deleted_at is not None:
                raise NotFoundError("partner not found for draft")

            # 1. Insert contact_log row
            contact_channel = _CHANNEL_MAP.get(sent_via, ContactChannel.other)
            summary = data.contact_summary or _summary_excerpt(draft.body)
            contact = contacts_repo.insert_contact(
                ctx.conn,
                partner_id=partner.id,
                contact_date=sent_at.date(),
                channel=contact_channel,
                initiated_by=data.initiated_by,
                summary=summary,
            )

            # 2. Advance partner.last_contact_date
            partners_repo.update_last_contact_date(
                ctx.conn, partner.id, sent_at.date()
            )

            # 3. Insert outreach_message
            msg = outreach_repo.insert_message(
                ctx.conn,
                draft_id=draft.id,
                partner_id=partner.id,
                contact_log_id=contact.id,
                sent_via=sent_via,
                recipient_handle=data.recipient_handle,
                subject_snapshot=draft.subject,
                body_snapshot=draft.body,
                version_sent=draft.version,
                sent_at=sent_at,
            )

            # 4. Flip draft to sent + back-pointer
            outreach_repo.attach_message_to_draft(ctx.conn, draft.id, msg.id)
            updated_draft = outreach_repo.get_draft_by_id(ctx.conn, draft.id)
            assert updated_draft is not None

            # 5. Audit
            AuditService.record(
                ctx,
                action=AuditAction.send,
                entity_type="outreach_message",
                entity_id=msg.id,
                entity_ulid=msg.ulid,
                before=None,
                after=msg.model_dump(mode="json"),
            )
            AuditService.record(
                ctx,
                action=AuditAction.log_contact,
                entity_type="contact",
                entity_id=contact.id,
                entity_ulid=contact.ulid,
                before=None,
                after=contact.model_dump(mode="json"),
            )

            # 6. Stage auto-advance (drafted/researched → sent)
            new_stage: OutreachStage | None = None
            if partner.outreach_stage in (OutreachStage.researched, OutreachStage.drafted):
                _set_stage_inline(ctx, partner, OutreachStage.sent)
                new_stage = OutreachStage.sent

            return {
                "message": msg.model_dump(mode="json"),
                "draft": updated_draft.model_dump(mode="json"),
                "contact": contact.model_dump(mode="json"),
                "partner_ulid": partner.ulid,
                "stage_advanced": new_stage is not None,
                "new_stage": new_stage.value if new_stage else partner.outreach_stage.value,
            }

    @staticmethod
    def set_stage(
        ctx: ServiceContext, partner_ulid: str, stage: OutreachStage
    ) -> PartnerRecord:
        with transaction(ctx.conn):
            partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if partner is None or partner.deleted_at is not None:
                raise NotFoundError(f"partner not found: {partner_ulid}")
            if partner.outreach_stage == stage:
                return partner
            return _set_stage_inline(ctx, partner, stage)


def _set_stage_inline(
    ctx: ServiceContext, partner: PartnerRecord, stage: OutreachStage
) -> PartnerRecord:
    """Sets partner.outreach_stage and writes a 'stage' audit row.

    Must be called from inside an outer transaction.
    """
    before = partner.model_dump(mode="json")
    updated = partners_repo.update_partner_fields(
        ctx.conn, partner.id, {"outreach_stage": stage.value}
    )
    assert updated is not None
    AuditService.record(
        ctx,
        action=AuditAction.stage,
        entity_type="partner",
        entity_id=partner.id,
        entity_ulid=partner.ulid,
        before={"outreach_stage": before.get("outreach_stage")},
        after={"outreach_stage": updated.outreach_stage.value},
    )
    return updated
