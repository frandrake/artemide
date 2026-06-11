"""AttachmentsService — file uploads stored as BLOBs inside SQLite.

The bytes ride inside the DB so `sqlite3 .backup` captures them automatically
(see scripts/backup.sh / /api/v1/admin/backup). Uploads are bounded by a mime
allowlist + a size cap, and de-duplicated by sha256 per target entity.

Content reads are NOT owner-gated — the n8n bot may download. Soft-delete and
restore remain owner-only (Rule 18 via assert_owner).
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from ..models import AttachmentEntityType, AttachmentRecord, AuditAction
from ..repository import attachments as attachments_repo
from ..repository import engagements as engagements_repo
from ..repository import firms as firms_repo
from ..repository import interviews as interviews_repo
from ..repository import orgs as orgs_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError
from .outbox_service import OutboxService


_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
}

_DEFAULT_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


def _max_bytes() -> int:
    try:
        return int(os.environ.get("ARTEMIDE_MAX_ATTACHMENT_BYTES", str(_DEFAULT_MAX_BYTES)))
    except ValueError:
        return _DEFAULT_MAX_BYTES


def _resolve_entity(ctx: ServiceContext, entity_type: AttachmentEntityType, entity_ulid: str) -> None:
    """Verify the target exists; raise NotFoundError otherwise."""
    if entity_type == AttachmentEntityType.firm:
        found = firms_repo.get_firm_by_ulid(ctx.conn, entity_ulid)
    elif entity_type == AttachmentEntityType.partner:
        found = partners_repo.get_partner_by_ulid(ctx.conn, entity_ulid)
    elif entity_type == AttachmentEntityType.org:
        found = orgs_repo.get_org_by_ulid(ctx.conn, entity_ulid)
    elif entity_type == AttachmentEntityType.engagement:
        found = engagements_repo.get_engagement_by_ulid(ctx.conn, entity_ulid)
    elif entity_type == AttachmentEntityType.interview:
        found = interviews_repo.get_interview_by_ulid(ctx.conn, entity_ulid)
    else:  # pragma: no cover - enum exhausted above
        found = None
    if found is None:
        raise NotFoundError(f"{entity_type.value} not found: {entity_ulid}")


def _meta_dict(rec: AttachmentRecord) -> dict[str, Any]:
    d = rec.model_dump(mode="json")
    return {k: v for k, v in d.items() if k != "created_at"}


class AttachmentsService:

    @staticmethod
    def upload(
        ctx: ServiceContext,
        *,
        entity_type: AttachmentEntityType,
        entity_ulid: str,
        kind: Any,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> AttachmentRecord:
        if content_type not in _ALLOWED_MIME:
            raise ValidationError(f"unsupported content type: {content_type}")
        cap = _max_bytes()
        if len(content) > cap:
            raise ValidationError(f"file exceeds {cap} byte limit")
        if len(content) == 0:
            raise ValidationError("empty file")

        with transaction(ctx.conn):
            _resolve_entity(ctx, entity_type, entity_ulid)
            digest = hashlib.sha256(content).hexdigest()

            # Idempotency: identical bytes already attached to this target →
            # return the existing record, no second audit/outbox row.
            existing = attachments_repo.find_live_by_entity_sha(
                ctx.conn, entity_type, entity_ulid, digest
            )
            if existing is not None:
                return existing

            rec = attachments_repo.insert_attachment(
                ctx.conn,
                entity_type=entity_type,
                entity_id=entity_ulid,
                kind=kind,
                filename=filename,
                content_type=content_type,
                content=content,
                sha256=digest,
                uploaded_by=ctx.actor,
            )
            search_repo.upsert_search_row(
                ctx.conn, entity_type="attachment", entity_ulid=rec.ulid,
                primary_text=rec.filename, secondary_text=rec.kind.value,
            )
            AuditService.record(
                ctx, action=AuditAction.attach, entity_type="attachment",
                entity_id=rec.id, entity_ulid=rec.ulid, after=_meta_dict(rec),
            )
            OutboxService.emit(
                ctx, event_type="attachment.added", entity_type="attachment",
                entity_ulid=rec.ulid,
                payload={
                    "entity_type": rec.entity_type.value,
                    "entity_ulid": rec.entity_id,
                    "kind": rec.kind.value,
                    "filename": rec.filename,
                    "byte_size": rec.byte_size,
                },
            )
            return rec

    @staticmethod
    def list_by_entity(
        ctx: ServiceContext, entity_type: AttachmentEntityType, entity_ulid: str
    ) -> list[AttachmentRecord]:
        return attachments_repo.list_by_entity(ctx.conn, entity_type, entity_ulid)

    @staticmethod
    def get_metadata(ctx: ServiceContext, ulid: str) -> AttachmentRecord:
        rec = attachments_repo.get_attachment_by_ulid(ctx.conn, ulid)
        if rec is None or rec.deleted_at is not None:
            raise NotFoundError(f"attachment not found: {ulid}")
        return rec

    @staticmethod
    def get_content(ctx: ServiceContext, ulid: str) -> tuple[bytes, str, str]:
        """Download bytes. Deliberately NOT owner-gated: the bot may read."""
        found = attachments_repo.get_content(ctx.conn, ulid)
        if found is None:
            raise NotFoundError(f"attachment not found: {ulid}")
        return found

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete attachment")
        with transaction(ctx.conn):
            rec = AttachmentsService.get_metadata(ctx, ulid)
            attachments_repo.soft_delete(ctx.conn, rec.id)
            search_repo.delete_search_row(ctx.conn, entity_type="attachment", entity_ulid=rec.ulid)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="attachment",
                entity_id=rec.id, entity_ulid=rec.ulid, before=_meta_dict(rec),
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> AttachmentRecord:
        assert_owner(ctx, operation="restore attachment")
        with transaction(ctx.conn):
            rec = attachments_repo.get_attachment_by_ulid(ctx.conn, ulid)
            if rec is None:
                raise NotFoundError(f"attachment not found: {ulid}")
            if rec.deleted_at is None:
                return rec
            attachments_repo.restore(ctx.conn, rec.id)
            restored = attachments_repo.get_attachment_by_ulid(ctx.conn, ulid) or rec
            search_repo.upsert_search_row(
                ctx.conn, entity_type="attachment", entity_ulid=restored.ulid,
                primary_text=restored.filename, secondary_text=restored.kind.value,
            )
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="attachment",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_meta_dict(restored),
            )
            return restored
