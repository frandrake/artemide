"""MessagesService — the outbound draft queue and the human approval gate.

Rule 17 (cardinal): messages are created only as 'proposed'; the transition to
'approved' is owner-only and emits message.approved. Artemide never sends —
an external consumer (n8n) sends and then calls mark_sent.
"""
from __future__ import annotations

from typing import Any

from ..models import (
    AuditAction,
    MessageEditInput,
    MessageRecord,
    MessageStatus,
    ProposeMessageInput,
)
from ..repository import engagements as engagements_repo
from ..repository import messages as messages_repo
from ..repository import partners as partners_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError
from .outbox_service import OutboxService


def _record_to_dict(m: MessageRecord) -> dict[str, Any]:
    d = m.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _transport_label(transport: str) -> str:
    if transport in ("rest", "api"):
        return "rest"
    if transport == "mcp":
        return "mcp"
    return "system"


class MessagesService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        status: Any = None,
        partner_ulid: str | None = None,
        engagement_ulid: str | None = None,
    ) -> list[MessageRecord]:
        partner_id = None
        if partner_ulid:
            partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if partner is None:
                raise NotFoundError(f"partner not found: {partner_ulid}")
            partner_id = partner.id
        engagement_id = None
        if engagement_ulid:
            e = engagements_repo.get_engagement_by_ulid(ctx.conn, engagement_ulid)
            if e is None:
                raise NotFoundError(f"engagement not found: {engagement_ulid}")
            engagement_id = e.id
        return messages_repo.list_messages(
            ctx.conn, status=status, partner_id=partner_id, engagement_id=engagement_id
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> MessageRecord:
        m = messages_repo.get_message_by_ulid(ctx.conn, ulid)
        if m is None:
            raise NotFoundError(f"message not found: {ulid}")
        return m

    @staticmethod
    def propose(ctx: ServiceContext, data: ProposeMessageInput) -> MessageRecord:
        with transaction(ctx.conn):
            # Rule 20: inbound idempotency on source_ref.
            if data.source_ref:
                existing = messages_repo.get_message_by_source_ref(ctx.conn, data.source_ref)
                if existing is not None:
                    return existing
            partner_id = None
            if data.partner_ulid:
                partner = partners_repo.get_partner_by_ulid(ctx.conn, data.partner_ulid)
                if partner is None:
                    raise NotFoundError(f"partner not found: {data.partner_ulid}")
                partner_id = partner.id
            engagement_id = None
            if data.engagement_ulid:
                e = engagements_repo.get_engagement_by_ulid(ctx.conn, data.engagement_ulid)
                if e is None:
                    raise NotFoundError(f"engagement not found: {data.engagement_ulid}")
                engagement_id = e.id
            m = messages_repo.insert_message(
                ctx.conn,
                body=data.body,
                kind=data.kind,
                partner_id=partner_id,
                engagement_id=engagement_id,
                channel=data.channel,
                recipient_hint=data.recipient_hint,
                subject=data.subject,
                rationale=data.rationale,
                source_ref=data.source_ref,
                created_by_transport=_transport_label(str(ctx.transport)),
            )
            AuditService.record(
                ctx, action=AuditAction.create, entity_type="message",
                entity_id=m.id, entity_ulid=m.ulid, after=_record_to_dict(m),
            )
            return m

    @staticmethod
    def edit(ctx: ServiceContext, ulid: str, data: MessageEditInput) -> MessageRecord:
        assert_owner(ctx, operation="edit message")
        with transaction(ctx.conn):
            m = MessagesService.get_by_ulid(ctx, ulid)
            if m.status in (MessageStatus.sent, MessageStatus.discarded):
                raise ConflictError(f"cannot edit a {m.status.value} message")
            before = _record_to_dict(m)
            messages_repo.update_body_subject(ctx.conn, m.id, subject=data.subject, body=data.body)
            updated = messages_repo.get_message_by_id(ctx.conn, m.id) or m
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="message",
                entity_id=m.id, entity_ulid=m.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def approve(ctx: ServiceContext, ulid: str) -> MessageRecord:
        # Rule 17: owner-only. A bot token is audited and rejected.
        assert_owner(ctx, operation="approve message")
        with transaction(ctx.conn):
            m = MessagesService.get_by_ulid(ctx, ulid)
            if m.status not in (MessageStatus.proposed, MessageStatus.edited):
                raise ConflictError(f"cannot approve a {m.status.value} message")
            before = _record_to_dict(m)
            messages_repo.mark_approved(ctx.conn, m.id)
            updated = messages_repo.get_message_by_id(ctx.conn, m.id) or m
            AuditService.record(
                ctx, action=AuditAction.approve, entity_type="message",
                entity_id=m.id, entity_ulid=m.ulid, before=before, after=_record_to_dict(updated),
            )
            OutboxService.emit(
                ctx, event_type="message.approved", entity_type="message",
                entity_ulid=m.ulid,
                payload={"kind": m.kind.value if m.kind else None,
                         "channel": m.channel.value if m.channel else None,
                         "subject": updated.subject},
            )
            return updated

    @staticmethod
    def mark_sent(ctx: ServiceContext, ulid: str) -> MessageRecord:
        with transaction(ctx.conn):
            m = MessagesService.get_by_ulid(ctx, ulid)
            if m.status != MessageStatus.approved:
                raise ConflictError("only an approved message can be marked sent")
            before = _record_to_dict(m)
            messages_repo.mark_sent(ctx.conn, m.id)
            updated = messages_repo.get_message_by_id(ctx.conn, m.id) or m
            AuditService.record(
                ctx, action=AuditAction.send, entity_type="message",
                entity_id=m.id, entity_ulid=m.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def discard(ctx: ServiceContext, ulid: str) -> MessageRecord:
        assert_owner(ctx, operation="discard message")
        with transaction(ctx.conn):
            m = MessagesService.get_by_ulid(ctx, ulid)
            if m.status == MessageStatus.sent:
                raise ConflictError("cannot discard a sent message")
            before = _record_to_dict(m)
            messages_repo.set_status(ctx.conn, m.id, MessageStatus.discarded)
            updated = messages_repo.get_message_by_id(ctx.conn, m.id) or m
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="message",
                entity_id=m.id, entity_ulid=m.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated
