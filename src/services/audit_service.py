"""Audit-log service. Every mutating service calls AuditService.record."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from ..models import (
    AuditAction,
    AuditLogRecord,
    AuditTransport,
    FirmTier,
    RelationshipState,
)
from ..repository import audit_log as audit_repo
from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from . import ServiceContext


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _serialise(payload: Any) -> str | None:
    if payload is None:
        return None
    if not isinstance(payload, (dict, list)):
        payload = dict(payload)
    return json.dumps(payload, default=_json_default, sort_keys=True)


@dataclass
class AuditDiff:
    audit_ulid: str
    action: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    fields_changed: list[str]


@dataclass
class CoverageEntry:
    firm_ulid: str
    firm_name: str
    has_active_partner: bool
    days_since_last_contact: int | None
    relationship_state: str
    flagged: bool
    note: str | None = None


@dataclass
class DormantEntry:
    partner_ulid: str
    partner_name: str
    firm_name: str
    tier: str
    days_since_last_contact: int


@dataclass
class FollowUpEntry:
    partner_ulid: str
    partner_name: str
    firm_name: str
    items: list[str]


@dataclass
class ReciprocityImbalance:
    partner_ulid: str
    partner_name: str
    firm_name: str
    given: int
    received: int


@dataclass
class AuditReport:
    generated_at: str
    primary_tier_coverage: list[CoverageEntry] = field(default_factory=list)
    specialist_tier_coverage: list[CoverageEntry] = field(default_factory=list)
    dormant_relationships: list[DormantEntry] = field(default_factory=list)
    open_follow_ups: list[FollowUpEntry] = field(default_factory=list)
    reciprocity_imbalances: list[ReciprocityImbalance] = field(default_factory=list)
    summary_actions: list[str] = field(default_factory=list)


_DORMANT_THRESHOLD = {FirmTier.primary: 180, FirmTier.specialist: 365}


class AuditService:
    """Audit-log read and write helpers + report generation."""

    @staticmethod
    def record(
        ctx: ServiceContext,
        action: AuditAction,
        entity_type: str,
        entity_id: int | str | None = None,
        entity_ulid: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        # Store the ULID as the durable entity_id reference (stable across renames).
        stored_entity_id = entity_ulid if entity_ulid is not None else (
            str(entity_id) if entity_id is not None else ""
        )
        payload_dict: dict[str, Any] = {}
        if before is not None:
            payload_dict["before"] = before
        if after is not None:
            payload_dict["after"] = after
        if entity_id is not None and entity_ulid is not None:
            payload_dict["entity_pk"] = entity_id
        payload = _serialise(payload_dict) if payload_dict else None

        return audit_repo.insert_audit_entry(
            ctx.conn,
            entity_type=entity_type,
            entity_id=stored_entity_id,
            action=action,
            actor=ctx.actor,
            transport=AuditTransport(ctx.transport) if not isinstance(ctx.transport, AuditTransport) else ctx.transport,
            payload=payload,
        )

    @staticmethod
    def list_recent(ctx: ServiceContext, limit: int = 50) -> list[AuditLogRecord]:
        return audit_repo.list_recent_audit_entries(ctx.conn, limit=limit)

    @staticmethod
    def list_by_entity(
        ctx: ServiceContext, entity_type: str, entity_id: int | str, *, limit: int = 50
    ) -> list[AuditLogRecord]:
        return audit_repo.list_audit_entries_by_entity(
            ctx.conn, entity_type, str(entity_id), limit=limit
        )

    @staticmethod
    def list_by_actor(ctx: ServiceContext, actor: str, *, limit: int = 50) -> list[AuditLogRecord]:
        return audit_repo.list_audit_entries_by_actor(ctx.conn, actor, limit=limit)

    @staticmethod
    def get_diff(ctx: ServiceContext, audit_ulid: str) -> AuditDiff | None:
        entry = audit_repo.get_audit_by_ulid(ctx.conn, audit_ulid)
        if entry is None:
            return None
        payload = json.loads(entry.payload) if entry.payload else {}
        before = payload.get("before")
        after = payload.get("after")
        changed: list[str] = []
        if isinstance(before, dict) and isinstance(after, dict):
            keys = set(before) | set(after)
            changed = sorted(k for k in keys if before.get(k) != after.get(k))
        elif before is None and isinstance(after, dict):
            changed = sorted(after.keys())
        elif isinstance(before, dict) and after is None:
            changed = sorted(before.keys())
        return AuditDiff(
            audit_ulid=entry.ulid,
            action=entry.action.value,
            before=before,
            after=after,
            fields_changed=changed,
        )

    @staticmethod
    def generate_report(ctx: ServiceContext) -> AuditReport:
        today = date.today()
        report = AuditReport(generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

        # Preload once — the report makes four passes over the same firms and
        # partners, which was a 4x N+1. Logic below is unchanged; it just reads
        # from these maps instead of re-querying per firm/partner.
        all_firms = firms_repo.list_firms(ctx.conn)
        partners_by_firm: dict[int, list] = {}
        for _p in partners_repo.list_all_partners(ctx.conn):
            partners_by_firm.setdefault(_p.firm_id, []).append(_p)
        value_counts = contacts_repo.value_counts_by_partner(ctx.conn)

        for tier, target in ((FirmTier.primary, report.primary_tier_coverage),
                              (FirmTier.specialist, report.specialist_tier_coverage)):
            for firm in (f for f in all_firms if f.tier == tier):
                firm_partners = partners_by_firm.get(firm.id, [])
                has_active = bool(firm_partners)
                last_contact_dates = [
                    p.last_contact_date for p in firm_partners if p.last_contact_date is not None
                ]
                days = None
                if last_contact_dates:
                    most_recent = max(last_contact_dates)
                    days = (today - most_recent).days
                flagged = False
                note = None
                if not has_active:
                    flagged = True
                    note = "no contactable partner"
                else:
                    threshold = 90 if tier == FirmTier.primary else 180
                    if days is None or days > threshold:
                        flagged = True
                        note = f"no contact in last {threshold}d"
                target.append(CoverageEntry(
                    firm_ulid=firm.ulid,
                    firm_name=firm.name,
                    has_active_partner=has_active,
                    days_since_last_contact=days,
                    relationship_state=firm.relationship_state.value,
                    flagged=flagged,
                    note=note,
                ))

        for firm in all_firms:
            tier_threshold = _DORMANT_THRESHOLD.get(firm.tier)
            if tier_threshold is None:
                continue
            for p in partners_by_firm.get(firm.id, []):
                if p.last_contact_date is None:
                    continue
                days = (today - p.last_contact_date).days
                if days > tier_threshold:
                    report.dormant_relationships.append(DormantEntry(
                        partner_ulid=p.ulid,
                        partner_name=p.name,
                        firm_name=firm.name,
                        tier=firm.tier.value,
                        days_since_last_contact=days,
                    ))

        for firm in all_firms:
            for p in partners_by_firm.get(firm.id, []):
                if not p.follow_ups_outstanding:
                    continue
                try:
                    items = json.loads(p.follow_ups_outstanding)
                except (TypeError, ValueError):
                    continue
                if isinstance(items, list) and items:
                    report.open_follow_ups.append(FollowUpEntry(
                        partner_ulid=p.ulid,
                        partner_name=p.name,
                        firm_name=firm.name,
                        items=[str(i) for i in items],
                    ))

        for firm in all_firms:
            for p in partners_by_firm.get(firm.id, []):
                given, received = value_counts.get(p.id, (0, 0))
                if given >= 3 and received == 0:
                    report.reciprocity_imbalances.append(ReciprocityImbalance(
                        partner_ulid=p.ulid,
                        partner_name=p.name,
                        firm_name=firm.name,
                        given=given,
                        received=received,
                    ))

        report.summary_actions = _summarise_actions(report)
        return report


def _summarise_actions(report: AuditReport) -> list[str]:
    actions: list[str] = []
    primary_gaps = [e for e in report.primary_tier_coverage if e.flagged]
    if primary_gaps:
        actions.append(
            f"Close {len(primary_gaps)} primary-tier coverage gap"
            + ("s" if len(primary_gaps) != 1 else "")
        )
    if report.dormant_relationships:
        actions.append(
            f"Re-engage or retire {len(report.dormant_relationships)} dormant relationship"
            + ("s" if len(report.dormant_relationships) != 1 else "")
        )
    if report.open_follow_ups:
        total = sum(len(f.items) for f in report.open_follow_ups)
        actions.append(f"Resolve {total} outstanding follow-up" + ("s" if total != 1 else ""))
    if report.reciprocity_imbalances:
        actions.append(
            f"Rebalance {len(report.reciprocity_imbalances)} one-sided relationship"
            + ("s" if len(report.reciprocity_imbalances) != 1 else "")
        )
    if not actions:
        actions.append("No urgent actions — relationship asset is healthy.")
    return actions[:5]
