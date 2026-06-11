"""InterviewsService — structured interview records + searchable transcripts.

Each logged interview also writes the existing one-line `engagement_log`
'interview' row (so the engagement timeline is unchanged) and links the two.
The transcript is indexed into search but never written to the audit ledger.
"""
from __future__ import annotations

from typing import Any

from ..models import (
    AuditAction,
    InterviewRecord,
    InterviewUpdateInput,
    LogInterviewInput,
    SetTranscriptInput,
)
from ..repository import engagements as engagements_repo
from ..repository import interviews as interviews_repo
from ..repository import search_index as search_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError
from .outbox_service import OutboxService


def _record_to_dict(rec: InterviewRecord) -> dict[str, Any]:
    """Audit/outbox view of an interview — excludes the transcript body (large
    and personal; the audit log is a diff ledger, not a content store) and the
    bookkeeping timestamps."""
    d = rec.model_dump(mode="json")
    return {
        k: v for k, v in d.items()
        if k not in ("transcript", "created_at", "updated_at")
    }


def _index(ctx: ServiceContext, rec: InterviewRecord) -> None:
    """Index round/summary as primary and summary+transcript as secondary so a
    transcript word is reachable via search_index MATCH."""
    parts = []
    if rec.round:
        parts.append(rec.round)
    if rec.summary:
        parts.append(rec.summary)
    primary = " — ".join(parts) if parts else f"Interview {rec.interview_date.isoformat()}"
    secondary = " ".join(p for p in (rec.summary, rec.transcript) if p)
    search_repo.upsert_search_row(
        ctx.conn, entity_type="interview", entity_ulid=rec.ulid,
        primary_text=primary, secondary_text=secondary,
    )


class InterviewsService:

    @staticmethod
    def log(ctx: ServiceContext, data: LogInterviewInput) -> InterviewRecord:
        with transaction(ctx.conn):
            engagement = engagements_repo.get_engagement_by_ulid(ctx.conn, data.engagement_ulid)
            if engagement is None:
                raise NotFoundError(f"engagement not found: {data.engagement_ulid}")

            # Reuse the existing engagement_log 'interview' path so the timeline
            # keeps its single source of truth.
            log = engagements_repo.insert_log(
                ctx.conn,
                engagement_id=engagement.id,
                event_date=data.interview_date,
                event_type="interview",
                summary=data.summary,
            )
            interview = interviews_repo.insert_interview(
                ctx.conn,
                engagement_id=engagement.id,
                engagement_log_id=log.id,
                interview_date=data.interview_date,
                round=data.round,
                format=data.format,
                panel=data.panel,
                summary=data.summary,
                transcript=data.transcript,
                transcript_source=data.transcript_source,
            )
            _index(ctx, interview)
            AuditService.record(
                ctx, action=AuditAction.interview, entity_type="interview",
                entity_id=interview.id, entity_ulid=interview.ulid,
                after=_record_to_dict(interview),
            )
            OutboxService.emit(
                ctx, event_type="interview.logged", entity_type="interview",
                entity_ulid=interview.ulid,
                payload={
                    "engagement_ulid": engagement.ulid,
                    "round": interview.round,
                    "format": interview.format.value if interview.format else None,
                },
            )
            if interview.transcript:
                OutboxService.emit(
                    ctx, event_type="interview.transcript_added",
                    entity_type="interview", entity_ulid=interview.ulid,
                    payload={"engagement_ulid": engagement.ulid},
                )
            return interview

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> InterviewRecord:
        rec = interviews_repo.get_interview_by_ulid(ctx.conn, ulid)
        if rec is None:
            raise NotFoundError(f"interview not found: {ulid}")
        return rec

    @staticmethod
    def get(ctx: ServiceContext, ulid: str, *, include_transcript: bool = False) -> InterviewRecord:
        rec = InterviewsService.get_by_ulid(ctx, ulid)
        if not include_transcript:
            rec = rec.model_copy(update={"transcript": None})
        return rec

    @staticmethod
    def list_by_engagement(ctx: ServiceContext, engagement_ulid: str) -> list[InterviewRecord]:
        engagement = engagements_repo.get_engagement_by_ulid(ctx.conn, engagement_ulid)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_ulid}")
        return interviews_repo.list_by_engagement(ctx.conn, engagement.id)

    @staticmethod
    def set_transcript(ctx: ServiceContext, data: SetTranscriptInput) -> InterviewRecord:
        with transaction(ctx.conn):
            rec = InterviewsService.get_by_ulid(ctx, data.interview_ulid)
            interviews_repo.set_transcript(
                ctx.conn, rec.id, data.transcript, data.transcript_source
            )
            updated = interviews_repo.get_interview_by_id(ctx.conn, rec.id) or rec
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.interview, entity_type="interview",
                entity_id=updated.id, entity_ulid=updated.ulid,
                after=_record_to_dict(updated),
            )
            OutboxService.emit(
                ctx, event_type="interview.transcript_added",
                entity_type="interview", entity_ulid=updated.ulid,
                payload={"interview_ulid": updated.ulid},
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: InterviewUpdateInput) -> InterviewRecord:
        with transaction(ctx.conn):
            rec = InterviewsService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            before = _record_to_dict(rec)
            updated = interviews_repo.update_fields(ctx.conn, rec.id, raw) or rec
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="interview",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete interview")
        with transaction(ctx.conn):
            rec = InterviewsService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(rec)
            interviews_repo.soft_delete(ctx.conn, rec.id)
            search_repo.delete_search_row(ctx.conn, entity_type="interview", entity_ulid=rec.ulid)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="interview",
                entity_id=rec.id, entity_ulid=rec.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> InterviewRecord:
        assert_owner(ctx, operation="restore interview")
        with transaction(ctx.conn):
            rec = interviews_repo.get_interview_by_ulid(ctx.conn, ulid)
            if rec is None:
                raise NotFoundError(f"interview not found: {ulid}")
            if rec.deleted_at is None:
                return rec
            interviews_repo.restore(ctx.conn, rec.id)
            restored = interviews_repo.get_interview_by_ulid(ctx.conn, ulid) or rec
            _index(ctx, restored)
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="interview",
                entity_id=restored.id, entity_ulid=restored.ulid,
                after=_record_to_dict(restored),
            )
            return restored
