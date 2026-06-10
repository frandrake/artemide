"""CompService — saved compensation scenarios and baseline comparison.

Every operation (reads included) is owner-only: package figures never leave
the owner role, so bot tokens get forbidden_role on the whole surface.
Deliberately no search-index or outbox integration — this data stays out of
the search corpus and the event stream.
"""
from __future__ import annotations

from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    CompareCompInput,
    CompScenarioRecord,
    CompScenarioUpdateInput,
    UpsertCompScenarioInput,
)
from ..repository import comp_scenarios as comp_repo
from ..repository import engagements as engagements_repo
from ..repository import orgs as orgs_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError

# Fields compared scenario-vs-baseline. pension_value_gbp and the totals are
# computed by _totals(); the rest are raw columns (None treated as 0).
COMPARE_FIELDS = (
    "base_gbp", "cash_bonus_gbp", "equity_gbp", "pension_value_gbp",
    "healthcare_gbp", "car_allowance_gbp", "other_gbp",
    "total_cash_gbp", "total_gbp",
)


def _record_to_dict(s: CompScenarioRecord) -> dict[str, Any]:
    d = s.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _totals(s: CompScenarioRecord) -> dict[str, int]:
    base = s.base_gbp or 0
    cash_bonus = s.cash_bonus_gbp or 0
    pension_value = round(base * (s.pension_pct or 0) / 100)
    total_cash = base + cash_bonus
    total = (
        total_cash + (s.equity_gbp or 0) + pension_value
        + (s.healthcare_gbp or 0) + (s.car_allowance_gbp or 0) + (s.other_gbp or 0)
    )
    return {
        "pension_value_gbp": pension_value,
        "total_cash_gbp": total_cash,
        "total_gbp": total,
    }


_RAW_COMPARE_FIELDS = (
    "base_gbp", "cash_bonus_gbp", "equity_gbp",
    "healthcare_gbp", "car_allowance_gbp", "other_gbp",
)


def _compare_values(s: CompScenarioRecord) -> dict[str, int]:
    return {**{f: getattr(s, f) or 0 for f in _RAW_COMPARE_FIELDS}, **_totals(s)}


class CompService:

    @staticmethod
    def to_payload(ctx: ServiceContext, s: CompScenarioRecord) -> dict[str, Any]:
        payload = to_response(s, extra_exclude={"engagement_id"})
        engagement = (
            engagements_repo.get_engagement_by_id(ctx.conn, s.engagement_id)
            if s.engagement_id is not None
            else None
        )
        payload["engagement_ulid"] = engagement.ulid if engagement else None
        payload["engagement_role_title"] = engagement.role_title if engagement else None
        org = (
            orgs_repo.get_org_by_id(ctx.conn, engagement.org_id) if engagement else None
        )
        payload["engagement_org_name"] = org.name if org else None
        payload["totals"] = _totals(s)
        return payload

    @staticmethod
    def list(
        ctx: ServiceContext, *, status: Any = None, include_deleted: bool = False
    ) -> list[CompScenarioRecord]:
        assert_owner(ctx, operation="list comp scenarios")
        return comp_repo.list_scenarios(ctx.conn, status=status, include_deleted=include_deleted)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> CompScenarioRecord:
        assert_owner(ctx, operation="read comp scenario")
        s = comp_repo.get_scenario_by_ulid(ctx.conn, ulid)
        if s is None:
            raise NotFoundError(f"comp scenario not found: {ulid}")
        return s

    @staticmethod
    def _resolve_engagement_id(ctx: ServiceContext, engagement_ulid: str | None) -> int | None:
        if engagement_ulid is None:
            return None
        engagement = engagements_repo.get_engagement_by_ulid(ctx.conn, engagement_ulid)
        if engagement is None:
            raise NotFoundError(f"engagement not found: {engagement_ulid}")
        return engagement.id

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertCompScenarioInput) -> CompScenarioRecord:
        assert_owner(ctx, operation="upsert comp scenario")
        with transaction(ctx.conn):
            engagement_id = CompService._resolve_engagement_id(ctx, data.engagement_ulid)

            existing = None
            if data.ulid:
                existing = comp_repo.get_scenario_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = comp_repo.get_scenario_by_name(ctx.conn, data.name)

            if existing is None:
                s = comp_repo.insert_scenario(
                    ctx.conn,
                    name=data.name,
                    status=data.status or "offer",
                    is_baseline=False,
                    engagement_id=engagement_id,
                    base_gbp=data.base_gbp,
                    cash_bonus_gbp=data.cash_bonus_gbp,
                    equity_gbp=data.equity_gbp,
                    equity_note=data.equity_note,
                    pension_pct=data.pension_pct,
                    healthcare_gbp=data.healthcare_gbp,
                    car_allowance_gbp=data.car_allowance_gbp,
                    other_gbp=data.other_gbp,
                    benefits_note=data.benefits_note,
                    ulid=data.ulid,
                )
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="comp_scenario",
                    entity_id=s.id, entity_ulid=s.ulid, after=_record_to_dict(s),
                )
                return s

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid", "engagement_ulid"})
            if data.engagement_ulid is not None:
                fields["engagement_id"] = engagement_id
            updated = comp_repo.update_scenario_fields(ctx.conn, existing.id, fields) or existing
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="comp_scenario",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(
        ctx: ServiceContext, ulid: str, data: CompScenarioUpdateInput
    ) -> CompScenarioRecord:
        assert_owner(ctx, operation="update comp scenario")
        with transaction(ctx.conn):
            s = comp_repo.get_scenario_by_ulid(ctx.conn, ulid)
            if s is None:
                raise NotFoundError(f"comp scenario not found: {ulid}")
            # exclude_unset (not exclude_none) so an explicit null clears a field.
            raw = data.model_dump(exclude_unset=True)
            if not raw:
                raise ValidationError("no fields supplied")
            if "engagement_ulid" in raw:
                raw["engagement_id"] = CompService._resolve_engagement_id(
                    ctx, raw.pop("engagement_ulid")
                )
            before = _record_to_dict(s)
            updated = comp_repo.update_scenario_fields(ctx.conn, s.id, raw) or s
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="comp_scenario",
                entity_id=s.id, entity_ulid=s.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def set_baseline(ctx: ServiceContext, ulid: str) -> CompScenarioRecord:
        assert_owner(ctx, operation="set comp baseline")
        with transaction(ctx.conn):
            s = comp_repo.get_scenario_by_ulid(ctx.conn, ulid)
            if s is None or s.deleted_at is not None:
                raise NotFoundError(f"comp scenario not found: {ulid}")
            before = _record_to_dict(s)
            comp_repo.set_baseline(ctx.conn, s.id)
            updated = comp_repo.get_scenario_by_id(ctx.conn, s.id) or s
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="comp_scenario",
                entity_id=s.id, entity_ulid=s.ulid, before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def compare(
        ctx: ServiceContext,
        *,
        scenario_ulids: list[str] | None = None,
        baseline_ulid: str | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation="compare comp scenarios")
        if baseline_ulid is not None:
            baseline = CompService.get_by_ulid(ctx, baseline_ulid)
            if baseline.deleted_at is not None:
                raise NotFoundError(f"comp scenario not found: {baseline_ulid}")
        else:
            baseline = comp_repo.get_baseline(ctx.conn)
            if baseline is None:
                raise NotFoundError("no baseline scenario set")

        if scenario_ulids is not None:
            scenarios = []
            for u in scenario_ulids:
                s = CompService.get_by_ulid(ctx, u)
                if s.deleted_at is not None:
                    raise NotFoundError(f"comp scenario not found: {u}")
                if s.id != baseline.id:
                    scenarios.append(s)
        else:
            scenarios = [
                s for s in comp_repo.list_scenarios(ctx.conn) if s.id != baseline.id
            ]

        base_values = _compare_values(baseline)

        out_scenarios = []
        for s in scenarios:
            values = _compare_values(s)
            deltas = {}
            for field in COMPARE_FIELDS:
                b = base_values[field]
                v = values[field]
                deltas[field] = {
                    "baseline": b,
                    "scenario": v,
                    "delta_gbp": v - b,
                    "delta_pct": round((v - b) / b * 100, 1) if b else None,
                }
            out_scenarios.append({**CompService.to_payload(ctx, s), "deltas": deltas})

        return {"baseline": CompService.to_payload(ctx, baseline), "scenarios": out_scenarios}

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete comp scenario")
        with transaction(ctx.conn):
            s = comp_repo.get_scenario_by_ulid(ctx.conn, ulid)
            if s is None or s.deleted_at is not None:
                raise NotFoundError(f"comp scenario not found: {ulid}")
            if s.is_baseline:
                raise ValidationError(
                    "cannot delete the baseline scenario; set another baseline first"
                )
            before = _record_to_dict(s)
            comp_repo.soft_delete_scenario(ctx.conn, s.id)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="comp_scenario",
                entity_id=s.id, entity_ulid=s.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> CompScenarioRecord:
        assert_owner(ctx, operation="restore comp scenario")
        with transaction(ctx.conn):
            s = comp_repo.get_scenario_by_ulid(ctx.conn, ulid)
            if s is None:
                raise NotFoundError(f"comp scenario not found: {ulid}")
            if s.deleted_at is None:
                return s
            live_same_name = comp_repo.get_scenario_by_name(ctx.conn, s.name)
            if live_same_name is not None:
                raise ConflictError(
                    f"a live scenario already uses the name: {s.name}"
                )
            # Never resurrect a second baseline.
            if s.is_baseline and comp_repo.get_baseline(ctx.conn) is not None:
                comp_repo.clear_baseline_flag(ctx.conn, s.id)
            comp_repo.restore_scenario(ctx.conn, s.id)
            restored = comp_repo.get_scenario_by_id(ctx.conn, s.id) or s
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="comp_scenario",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
