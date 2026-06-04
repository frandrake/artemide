"""EngagementsService — the pipeline of roles in motion."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import (
    AdvanceStageInput,
    AuditAction,
    CloseEngagementInput,
    EngagementInterest,
    EngagementRecord,
    EngagementUpdateInput,
    ENGAGEMENT_STAGE_ORDER,
    UpsertEngagementInput,
)
from ..repository import engagements as engagements_repo
from ..repository import orgs as orgs_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from .fit_service import FitService, ProfileMissingError
from .outbox_service import OutboxService


def _record_to_dict(e: EngagementRecord) -> dict[str, Any]:
    d = e.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _index(ctx: ServiceContext, e: EngagementRecord) -> None:
    org = orgs_repo.get_org_by_id(ctx.conn, e.org_id)
    org_name = org.name if org else ""
    secondary = " ".join(p for p in (org_name, e.next_step, e.comp_equity_note) if p)
    search_repo.upsert_search_row(
        ctx.conn, entity_type="engagement", entity_ulid=e.ulid,
        primary_text=e.role_title, secondary_text=secondary,
    )


def _today() -> date:
    return date.today()


class EngagementsService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        stage: Any = None,
        interest: Any = None,
        org_ulid: str | None = None,
        source_partner_ulid: str | None = None,
        sort: str | None = None,
    ) -> list[EngagementRecord]:
        org_id = None
        if org_ulid:
            org = orgs_repo.get_org_by_ulid(ctx.conn, org_ulid)
            if org is None:
                raise NotFoundError(f"organisation not found: {org_ulid}")
            org_id = org.id
        partner_id = None
        if source_partner_ulid:
            partner = partners_repo.get_partner_by_ulid(ctx.conn, source_partner_ulid)
            if partner is None:
                raise NotFoundError(f"partner not found: {source_partner_ulid}")
            partner_id = partner.id
        return engagements_repo.list_engagements(
            ctx.conn, stage=stage, interest=interest, org_id=org_id,
            source_partner_id=partner_id, sort=sort,
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> EngagementRecord:
        e = engagements_repo.get_engagement_by_ulid(ctx.conn, ulid)
        if e is None:
            raise NotFoundError(f"engagement not found: {ulid}")
        return e

    @staticmethod
    def _rescore_safe(ctx: ServiceContext, engagement: EngagementRecord) -> EngagementRecord:
        try:
            FitService.rescore(ctx, engagement)
        except ProfileMissingError:
            pass  # no active profile yet — leave fit unscored
        return engagements_repo.get_engagement_by_id(ctx.conn, engagement.id) or engagement

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertEngagementInput) -> EngagementRecord:
        with transaction(ctx.conn):
            org = orgs_repo.get_org_by_ulid(ctx.conn, data.org_ulid)
            if org is None:
                raise NotFoundError(f"organisation not found: {data.org_ulid}")
            partner_id = None
            if data.source_partner_ulid:
                partner = partners_repo.get_partner_by_ulid(ctx.conn, data.source_partner_ulid)
                if partner is None:
                    raise NotFoundError(f"partner not found: {data.source_partner_ulid}")
                partner_id = partner.id

            existing = None
            if data.ulid:
                existing = engagements_repo.get_engagement_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = engagements_repo.get_engagement_by_org_and_title(
                    ctx.conn, org.id, data.role_title
                )

            if existing is None:
                e = engagements_repo.insert_engagement(
                    ctx.conn,
                    org_id=org.id,
                    role_title=data.role_title,
                    role_type=data.role_type,
                    source=data.source,
                    source_partner_id=partner_id,
                    stage=data.stage or "surfaced",
                    interest=data.interest or "exploratory",
                    comp_base_gbp=data.comp_base_gbp,
                    comp_total_gbp=data.comp_total_gbp,
                    comp_equity_note=data.comp_equity_note,
                    next_step=data.next_step,
                    next_step_date=data.next_step_date,
                    ulid=data.ulid,
                )
                e = EngagementsService._rescore_safe(ctx, e)
                _index(ctx, e)
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="engagement",
                    entity_id=e.id, entity_ulid=e.ulid, after=_record_to_dict(e),
                )
                OutboxService.emit(
                    ctx, event_type="engagement.surfaced", entity_type="engagement",
                    entity_ulid=e.ulid,
                    payload={"org_ulid": org.ulid, "role_title": e.role_title, "fit_score": e.fit_score},
                )
                return e

            before = _record_to_dict(existing)
            fields = data.model_dump(
                exclude_none=True,
                exclude={"ulid", "org_ulid", "role_title", "source_partner_ulid", "stage", "tags"},
            )
            updated = engagements_repo.update_engagement_fields(ctx.conn, existing.id, fields) or existing
            updated = EngagementsService._rescore_safe(ctx, updated)
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="engagement",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: EngagementUpdateInput) -> EngagementRecord:
        with transaction(ctx.conn):
            e = EngagementsService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            before = _record_to_dict(e)
            updated = engagements_repo.update_engagement_fields(ctx.conn, e.id, raw) or e
            updated = EngagementsService._rescore_safe(ctx, updated)
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="engagement",
                entity_id=e.id, entity_ulid=e.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def set_interest(ctx: ServiceContext, ulid: str, interest: EngagementInterest) -> EngagementRecord:
        return EngagementsService.update_fields(ctx, ulid, EngagementUpdateInput(interest=interest))

    @staticmethod
    def _check_forward(current: str, to_stage: str) -> None:
        """Rule 14: forward-only along the stage order. Closing is handled
        separately (routed through close()), so it never reaches here."""
        if to_stage == "closed":
            # Unreachable via advance_stage (which delegates closing to close());
            # guard defensively so no path can close without a closed_reason.
            raise InvalidStateTransitionError("use close() to close an engagement")
        if current == "closed":
            raise InvalidStateTransitionError("cannot advance a closed engagement")
        if to_stage not in ENGAGEMENT_STAGE_ORDER:
            raise InvalidStateTransitionError(f"unknown stage: {to_stage}")
        if ENGAGEMENT_STAGE_ORDER.index(to_stage) <= ENGAGEMENT_STAGE_ORDER.index(current):
            raise InvalidStateTransitionError(
                f"stage must move forward: {current} → {to_stage}"
            )

    @staticmethod
    def advance_stage(ctx: ServiceContext, ulid: str, data: AdvanceStageInput) -> EngagementRecord:
        if data.to_stage.value == "closed":
            # Closing must capture a reason and flow through the single close()
            # path (Rule 14) — advancing to 'closed' previously left
            # closed_reason NULL and then permanently blocked close().
            if data.closed_reason is None:
                raise ValidationError(
                    "closing an engagement requires closed_reason (or use the close operation)"
                )
            return EngagementsService.close(
                ctx, ulid,
                CloseEngagementInput(closed_reason=data.closed_reason, summary=data.summary),
            )
        with transaction(ctx.conn):
            e = EngagementsService.get_by_ulid(ctx, ulid)
            from_stage = e.stage.value
            to_stage = data.to_stage.value
            EngagementsService._check_forward(from_stage, to_stage)
            before = _record_to_dict(e)
            engagements_repo.set_stage(ctx.conn, e.id, to_stage)
            engagements_repo.insert_log(
                ctx.conn, engagement_id=e.id, event_date=_today(),
                event_type="stage_change", from_stage=from_stage, to_stage=to_stage,
                summary=data.summary,
            )
            updated = engagements_repo.get_engagement_by_id(ctx.conn, e.id) or e
            AuditService.record(
                ctx, action=AuditAction.stage, entity_type="engagement",
                entity_id=e.id, entity_ulid=e.ulid, before=before, after=_record_to_dict(updated),
            )
            OutboxService.emit(
                ctx, event_type="engagement.stage_changed", entity_type="engagement",
                entity_ulid=e.ulid,
                payload={"from_stage": from_stage, "to_stage": to_stage, "summary": data.summary},
            )
            EngagementsService._after_advance(ctx, updated)
            return updated

    @staticmethod
    def close(ctx: ServiceContext, ulid: str, data: CloseEngagementInput) -> EngagementRecord:
        with transaction(ctx.conn):
            e = EngagementsService.get_by_ulid(ctx, ulid)
            if e.stage.value == "closed":
                raise InvalidStateTransitionError("engagement already closed")
            from_stage = e.stage.value
            before = _record_to_dict(e)
            engagements_repo.set_closed(ctx.conn, e.id, data.closed_reason)
            engagements_repo.insert_log(
                ctx.conn, engagement_id=e.id, event_date=_today(),
                event_type="stage_change", from_stage=from_stage, to_stage="closed",
                summary=data.summary,
            )
            updated = engagements_repo.get_engagement_by_id(ctx.conn, e.id) or e
            AuditService.record(
                ctx, action=AuditAction.stage, entity_type="engagement",
                entity_id=e.id, entity_ulid=e.ulid, before=before, after=_record_to_dict(updated),
            )
            OutboxService.emit(
                ctx, event_type="engagement.stage_changed", entity_type="engagement",
                entity_ulid=e.ulid,
                payload={"from_stage": from_stage, "to_stage": "closed",
                         "closed_reason": data.closed_reason.value},
            )
            return updated

    @staticmethod
    def _after_advance(ctx: ServiceContext, engagement: EngagementRecord) -> None:
        """Side-effects of reaching a stage (Rule 14). Reaching 'offer' nudges the
        close milestone toward done. Best-effort — never fails the advance."""
        if engagement.stage.value == "offer":
            try:
                from .programme_service import ProgrammeService

                ProgrammeService.note_offer_reached(ctx)
            except Exception:  # pragma: no cover - defensive
                pass

    @staticmethod
    def rescore(ctx: ServiceContext, ulid: str) -> EngagementRecord:
        e = EngagementsService.get_by_ulid(ctx, ulid)
        with transaction(ctx.conn):
            return EngagementsService._rescore_safe(ctx, e)

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete engagement")
        with transaction(ctx.conn):
            e = EngagementsService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(e)
            engagements_repo.soft_delete_engagement(ctx.conn, e.id)
            search_repo.delete_search_row(ctx.conn, entity_type="engagement", entity_ulid=e.ulid)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="engagement",
                entity_id=e.id, entity_ulid=e.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> EngagementRecord:
        assert_owner(ctx, operation="restore engagement")
        with transaction(ctx.conn):
            e = engagements_repo.get_engagement_by_ulid(ctx.conn, ulid)
            if e is None:
                raise NotFoundError(f"engagement not found: {ulid}")
            if e.deleted_at is None:
                return e
            engagements_repo.restore_engagement(ctx.conn, e.id)
            restored = engagements_repo.get_engagement_by_ulid(ctx.conn, ulid) or e
            _index(ctx, restored)
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="engagement",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
