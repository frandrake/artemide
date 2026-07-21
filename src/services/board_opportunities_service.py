"""BoardOpportunitiesService — the board/NED seats in motion.

Owner-only; no outbox, no shared search index. Home of:
  R1 (conflict gate) — ADVISORY: advancing past 'conflict_screen' while
      conflict_cleared != 'yes' is allowed but returns a warning (it does not
      block, per the chosen policy).
  R3 (stage audit) — every stage change is written to board_opportunity_log
      AND audit_log (the dual trail mirrors engagements).
The stage machine itself stays forward-only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import (
    AdvanceBoardStageInput,
    AuditAction,
    BoardOppEventType,
    BoardOpportunityRecord,
    BoardOpportunityUpdateInput,
    BOARD_STAGE_ORDER,
    SetBoardOutcomeInput,
    UpsertBoardOpportunityInput,
)
from ..api._serde import to_response
from ..repository import board_contacts as contacts_repo
from ..repository import board_firms as firms_repo
from ..repository import board_opportunities as opportunities_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import InvalidStateTransitionError, NotFoundError, ValidationError

_CONFLICT_SCREEN_INDEX = BOARD_STAGE_ORDER.index("conflict_screen")

_EXCLUDE = {"source_firm_id", "chair_contact_id"}

_ADVISORY_CATEGORIES = {"advisory_board", "editorial_board"}
_LEGACY_ROLE_CATEGORY = {
    "ned": "ned_unspecified",
    "sid": "senior_independent_director",
    "committee": "committee_member",
    "trustee": "trustee",
    "adviser": "advisory_board",
}


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _normalise_governance(
    category: Any, fiduciary_status: Any, *, legacy_role: Any = None,
) -> tuple[Any, Any]:
    """Return a conservative canonical category/status pair.

    Legacy labels are mapped without inventing NED independence. Advisory and
    editorial seats are always marked contractual/non-fiduciary and an explicit
    contradictory request is rejected.
    """
    if category is None and legacy_role is not None:
        category = _LEGACY_ROLE_CATEGORY.get(_value(legacy_role))
    category_value = _value(category)
    status_value = _value(fiduciary_status)
    if category_value in _ADVISORY_CATEGORIES:
        if status_value == "statutory_fiduciary":
            raise ValidationError(
                "advisory and editorial board appointments must be recorded as non-fiduciary"
            )
        fiduciary_status = "contractual_non_fiduciary"
    return category, fiduciary_status


def _record_to_dict(o: BoardOpportunityRecord) -> dict[str, Any]:
    d = o.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


class BoardOpportunitiesService:

    @staticmethod
    def to_payload(ctx: ServiceContext, o: BoardOpportunityRecord) -> dict[str, Any]:
        payload = to_response(o, extra_exclude=_EXCLUDE)
        firm = firms_repo.get_firm_by_id(ctx.conn, o.source_firm_id) if o.source_firm_id is not None else None
        payload["source_firm_ulid"] = firm.ulid if firm else None
        payload["source_firm_name"] = firm.name if firm else None
        chair = contacts_repo.get_contact_by_id(ctx.conn, o.chair_contact_id) if o.chair_contact_id is not None else None
        payload["chair_contact_ulid"] = chair.ulid if chair else None
        payload["chair_name"] = chair.name if chair else None
        return payload

    @staticmethod
    def _resolve_firm_id(ctx: ServiceContext, firm_ulid: str | None) -> int | None:
        if firm_ulid is None:
            return None
        firm = firms_repo.get_firm_by_ulid(ctx.conn, firm_ulid)
        if firm is None:
            raise NotFoundError(f"board firm not found: {firm_ulid}")
        return firm.id

    @staticmethod
    def _resolve_chair_id(ctx: ServiceContext, contact_ulid: str | None) -> int | None:
        if contact_ulid is None:
            return None
        contact = contacts_repo.get_contact_by_ulid(ctx.conn, contact_ulid)
        if contact is None:
            raise NotFoundError(f"board contact not found: {contact_ulid}")
        return contact.id

    @staticmethod
    def list(
        ctx: ServiceContext, *, stage: Any = None, interest: Any = None,
        conflict_cleared: Any = None, sort: str | None = None,
    ) -> list[BoardOpportunityRecord]:
        assert_owner(ctx, operation="list board opportunities")
        return opportunities_repo.list_opportunities(
            ctx.conn, stage=stage, interest=interest, conflict_cleared=conflict_cleared, sort=sort
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> BoardOpportunityRecord:
        assert_owner(ctx, operation="read board opportunity")
        o = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid)
        if o is None:
            raise NotFoundError(f"board opportunity not found: {ulid}")
        return o

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertBoardOpportunityInput) -> BoardOpportunityRecord:
        assert_owner(ctx, operation="upsert board opportunity")
        with transaction(ctx.conn):
            source_firm_id = BoardOpportunitiesService._resolve_firm_id(ctx, data.source_firm_ulid)
            chair_contact_id = BoardOpportunitiesService._resolve_chair_id(ctx, data.chair_contact_ulid)

            existing = None
            if data.ulid:
                existing = opportunities_repo.get_opportunity_by_ulid(ctx.conn, data.ulid)

            if existing is None:
                appointment_category, fiduciary_status = _normalise_governance(
                    data.appointment_category, data.fiduciary_status,
                    legacy_role=data.role,
                )
                o = opportunities_repo.insert_opportunity(
                    ctx.conn,
                    organisation=data.organisation,
                    board_type=data.board_type,
                    role=data.role,
                    appointment_category=appointment_category,
                    fiduciary_status=fiduciary_status,
                    legal_entity=data.legal_entity,
                    time_commitment_days=data.time_commitment_days,
                    term_length_months=data.term_length_months,
                    annual_fee_gbp=data.annual_fee_gbp,
                    committee_expectations=data.committee_expectations,
                    independence_requirement=data.independence_requirement,
                    liability_indemnity_notes=data.liability_indemnity_notes,
                    do_insurance_status=data.do_insurance_status,
                    conflicts_notes=data.conflicts_notes,
                    due_diligence_notes=data.due_diligence_notes,
                    next_step_due_date=data.next_step_due_date,
                    source_firm_id=source_firm_id,
                    source_text=data.source_text,
                    chair_contact_id=chair_contact_id,
                    date_surfaced=data.date_surfaced,
                    stage=data.stage or "surfaced",
                    interest=data.interest or "exploratory",
                    next_step=data.next_step,
                    notes=data.notes,
                    ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="board_opportunity",
                    entity_id=o.id, entity_ulid=o.ulid, after=_record_to_dict(o),
                )
                return o

            before = _record_to_dict(existing)
            fields = data.model_dump(
                exclude_none=True,
                exclude={"ulid", "source_firm_ulid", "chair_contact_ulid", "stage"},
            )
            if data.source_firm_ulid is not None:
                fields["source_firm_id"] = source_firm_id
            if data.chair_contact_ulid is not None:
                fields["chair_contact_id"] = chair_contact_id
            category, status = _normalise_governance(
                fields.get("appointment_category", existing.appointment_category),
                fields.get("fiduciary_status", existing.fiduciary_status),
                legacy_role=fields.get("role", existing.role),
            )
            if category is not None:
                fields["appointment_category"] = category
            if status is not None:
                fields["fiduciary_status"] = status
            updated = opportunities_repo.update_opportunity_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_opportunity",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: BoardOpportunityUpdateInput) -> BoardOpportunityRecord:
        assert_owner(ctx, operation="update board opportunity")
        with transaction(ctx.conn):
            o = BoardOpportunitiesService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_unset=True)
            if raw.get("fiduciary_status") is None and "fiduciary_status" in raw:
                raise ValidationError("fiduciary_status cannot be cleared")
            if raw.get("do_insurance_status") is None and "do_insurance_status" in raw:
                raise ValidationError("do_insurance_status cannot be cleared")
            if not raw:
                raise ValidationError("no fields supplied")
            if "source_firm_ulid" in raw:
                raw["source_firm_id"] = BoardOpportunitiesService._resolve_firm_id(ctx, raw.pop("source_firm_ulid"))
            if "chair_contact_ulid" in raw:
                raw["chair_contact_id"] = BoardOpportunitiesService._resolve_chair_id(ctx, raw.pop("chair_contact_ulid"))
            category, status = _normalise_governance(
                raw.get("appointment_category", o.appointment_category),
                raw.get("fiduciary_status", o.fiduciary_status),
                legacy_role=raw.get("role", o.role),
            )
            if category is not None:
                raw["appointment_category"] = category
            if status is not None:
                raw["fiduciary_status"] = status
            before = _record_to_dict(o)
            updated = opportunities_repo.update_opportunity_fields(ctx.conn, o.id, raw) or o
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_opportunity",
                entity_id=o.id, entity_ulid=o.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def _check_forward(current: str, to_stage: str) -> None:
        """Forward-only along BOARD_STAGE_ORDER (this is a hard rule; only the
        conflict-clearance check is advisory)."""
        if to_stage not in BOARD_STAGE_ORDER:
            raise InvalidStateTransitionError(f"unknown stage: {to_stage}")
        if BOARD_STAGE_ORDER.index(to_stage) <= BOARD_STAGE_ORDER.index(current):
            raise InvalidStateTransitionError(f"stage must move forward: {current} → {to_stage}")

    @staticmethod
    def advance_stage(
        ctx: ServiceContext, ulid: str, data: AdvanceBoardStageInput
    ) -> tuple[BoardOpportunityRecord, list[str]]:
        """Advance forward one or more stages. Returns (record, warnings).

        R1 is advisory: advancing past 'conflict_screen' with conflict_cleared
        != 'yes' is permitted but surfaces a warning rather than raising.
        """
        assert_owner(ctx, operation="advance board opportunity")
        with transaction(ctx.conn):
            o = BoardOpportunitiesService.get_by_ulid(ctx, ulid)
            if o.outcome is not None:
                raise InvalidStateTransitionError(
                    f"board opportunity is terminal (outcome={o.outcome.value})"
                )
            from_stage = o.stage.value
            to_stage = data.to_stage.value
            BoardOpportunitiesService._check_forward(from_stage, to_stage)

            warnings: list[str] = []
            if (
                BOARD_STAGE_ORDER.index(to_stage) > _CONFLICT_SCREEN_INDEX
                and o.conflict_cleared.value != "yes"
            ):
                warnings.append(
                    "conflict screen not cleared (conflict_cleared="
                    f"{o.conflict_cleared.value}); advancing past conflict_screen is advisory-gated"
                )

            before = _record_to_dict(o)
            opportunities_repo.set_stage(ctx.conn, o.id, to_stage)
            opportunities_repo.insert_log(
                ctx.conn, opportunity_id=o.id, event_date=date.today(),
                event_type=BoardOppEventType.stage_change,
                from_stage=from_stage, to_stage=to_stage, summary=data.summary,
            )
            updated = opportunities_repo.get_opportunity_by_id(ctx.conn, o.id) or o
            AuditService.record(
                ctx, action=AuditAction.stage, entity_type="board_opportunity",
                entity_id=o.id, entity_ulid=o.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated, warnings

    @staticmethod
    def set_outcome(
        ctx: ServiceContext, ulid: str, data: SetBoardOutcomeInput
    ) -> BoardOpportunityRecord:
        """Record how a seat ended (accepted / declined / lost).

        Allowed from any stage — a process can die before 'decision' — and
        logged to both trails (R3 pattern). Feeds the board target read-out.
        """
        assert_owner(ctx, operation="set board opportunity outcome")
        with transaction(ctx.conn):
            o = BoardOpportunitiesService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(o)
            opportunities_repo.set_outcome(ctx.conn, o.id, data.outcome)
            opportunities_repo.insert_log(
                ctx.conn, opportunity_id=o.id, event_date=date.today(),
                event_type=BoardOppEventType.note,
                summary=data.summary or f"outcome recorded: {data.outcome.value}",
            )
            updated = opportunities_repo.get_opportunity_by_id(ctx.conn, o.id) or o
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_opportunity",
                entity_id=o.id, entity_ulid=o.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete board opportunity")
        with transaction(ctx.conn):
            o = BoardOpportunitiesService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(o)
            opportunities_repo.soft_delete_opportunity(ctx.conn, o.id)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="board_opportunity",
                entity_id=o.id, entity_ulid=o.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> BoardOpportunityRecord:
        assert_owner(ctx, operation="restore board opportunity")
        with transaction(ctx.conn):
            o = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid)
            if o is None:
                raise NotFoundError(f"board opportunity not found: {ulid}")
            if o.deleted_at is None:
                return o
            opportunities_repo.restore_opportunity(ctx.conn, o.id)
            restored = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid) or o
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="board_opportunity",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
