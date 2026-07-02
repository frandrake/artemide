"""Service-layer tests."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.models import (
    AuditAction,
    CalendarStatus,
    ContactChannel,
    FirmTier,
    InitiatedBy,
    NoteEntityType,
    OutreachStage,
    RelationshipState,
)
from src.repository import firms as firms_repo
from src.services import ServiceContext
from src.services.audit_service import AuditService
from src.services.contacts_service import ContactsService
from src.services.exceptions import InvalidStateTransitionError
from src.services.export_service import ExportService
from src.services.firms_service import FirmsService
from src.services.import_service import ImportService
from src.services.notes_service import NotesService
from src.services.partners_service import PartnersService
from src.services.planning_service import PlanningService
from src.services.search_service import SearchService


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="system")


def _seed_firm(ctx, *, name, tier, **kw):
    firm = firms_repo.insert_firm(ctx.conn, name=name, tier=tier, **kw)
    return FirmsService.get_by_ulid(ctx, firm.ulid)


def test_audit_record_and_diff(ctx):
    firm = _seed_firm(ctx, name="TML Partners", tier=FirmTier.specialist)
    entry = AuditService.record(
        ctx,
        action=AuditAction.update,
        entity_type="firm",
        entity_id=firm.id,
        entity_ulid=firm.ulid,
        before={"relationship_state": "cold"},
        after={"relationship_state": "warming"},
    )
    diff = AuditService.get_diff(ctx, entry.ulid)
    assert diff is not None
    assert diff.fields_changed == ["relationship_state"]
    assert diff.before == {"relationship_state": "cold"}
    assert diff.after == {"relationship_state": "warming"}


def test_firms_state_transition_illegal_cold_to_warm(ctx):
    firm = _seed_firm(ctx, name="Spencer Stuart", tier=FirmTier.primary)
    with pytest.raises(InvalidStateTransitionError):
        FirmsService.update_state(ctx, firm.ulid, RelationshipState.warm)


def test_firms_state_transition_legal_cold_to_warming(ctx):
    firm = _seed_firm(ctx, name="Korn Ferry", tier=FirmTier.primary)
    updated = FirmsService.update_state(ctx, firm.ulid, RelationshipState.warming)
    assert updated.relationship_state == RelationshipState.warming
    audits = AuditService.list_by_entity(ctx, "firm", firm.ulid)
    assert len(audits) == 1
    assert audits[0].action == AuditAction.update


def test_partner_upsert_create_then_update_distinct_audit_entries(ctx):
    firm = _seed_firm(ctx, name="Egon Zehnder", tier=FirmTier.primary)
    p1 = PartnersService.upsert(ctx, firm.name, "Elena Brescia", title="Partner")
    p2 = PartnersService.upsert(ctx, firm.name, "Elena Brescia", title="Consultant")
    assert p1.ulid == p2.ulid

    audits = AuditService.list_by_entity(ctx, "partner", p1.ulid)
    actions = [a.action for a in audits]
    assert AuditAction.create in actions
    assert AuditAction.update in actions


def test_contact_log_advances_state_and_updates_last_contact(ctx):
    firm = _seed_firm(ctx, name="Heidrick & Struggles", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Marcus Penrose")
    assert partner.relationship_state == RelationshipState.cold

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 5, 1),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        value_given="Shared market-mapping doc",
        summary="First outreach",
        advance_state=True,
    )
    assert resp.contact.partner_id == partner.id
    assert resp.partner.last_contact_date == date(2026, 5, 1)
    assert resp.state_advanced is True
    assert resp.new_state == RelationshipState.warming


def test_contact_log_no_advance_without_value(ctx):
    firm = _seed_firm(ctx, name="Russell Reynolds", tier=FirmTier.primary)
    PartnersService.upsert(ctx, firm.name, "James Donlan")
    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name="James Donlan",
        contact_date=date(2026, 5, 2),
        channel=ContactChannel.call,
        initiated_by=InitiatedBy.me,
        summary="Quick hello",
        advance_state=True,
    )
    assert resp.state_advanced is False
    assert resp.partner.last_contact_date == date(2026, 5, 2)


def test_planning_list_due_touches_respects_thresholds(ctx):
    primary = _seed_firm(ctx, name="TML Primary Demo", tier=FirmTier.primary)
    specialist = _seed_firm(ctx, name="Specialist Co", tier=FirmTier.specialist)

    today = date.today()
    p_primary_overdue = PartnersService.upsert(
        ctx, primary.name, "Overdue Primary",
        next_touch_date=today + timedelta(days=300),
    )
    from src.repository import partners as partners_repo
    partners_repo.update_partner_fields(
        ctx.conn, p_primary_overdue.id,
        {"last_contact_date": today - timedelta(days=125)},
    )
    p_specialist_ok = PartnersService.upsert(
        ctx, specialist.name, "Recent Specialist",
        next_touch_date=today + timedelta(days=300),
    )
    partners_repo.update_partner_fields(
        ctx.conn, p_specialist_ok.id,
        {"last_contact_date": today - timedelta(days=125)},
    )

    due = PlanningService.list_due_touches(ctx, window_days=14)
    statuses = {(d.partner_name, d.status) for d in due}
    assert ("Overdue Primary", "overdue") in statuses
    assert not any(name == "Recent Specialist" for name, _ in statuses)


def test_contact_log_advances_stage_outbound_to_sent(ctx):
    firm = _seed_firm(ctx, name="Stage Firm A", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Stage Partner A")
    assert partner.outreach_stage == OutreachStage.researched

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 1),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="Sent intro note",
    )
    assert resp.stage_advanced is True
    assert resp.new_stage == OutreachStage.sent
    assert resp.partner.outreach_stage == OutreachStage.sent


def test_contact_log_advances_stage_inbound_to_replied(ctx):
    firm = _seed_firm(ctx, name="Stage Firm B", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Stage Partner B")

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 2),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.them,
        summary="They replied",
    )
    assert resp.new_stage == OutreachStage.replied


def test_contact_log_realtime_channel_advances_to_met(ctx):
    firm = _seed_firm(ctx, name="Stage Firm C", tier=FirmTier.specialist)
    partner = PartnersService.upsert(ctx, firm.name, "Stage Partner C")

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 3),
        channel=ContactChannel.coffee,
        initiated_by=InitiatedBy.me,
        summary="Coffee in Mayfair",
    )
    assert resp.new_stage == OutreachStage.met


def test_contact_log_never_moves_stage_backwards_or_from_ongoing(ctx):
    from src.repository import partners as partners_repo

    firm = _seed_firm(ctx, name="Stage Firm D", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Stage Partner D")
    partners_repo.update_partner_fields(
        ctx.conn, partner.id, {"outreach_stage": OutreachStage.ongoing},
    )

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 4),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="Check-in",
    )
    assert resp.stage_advanced is False
    assert resp.partner.outreach_stage == OutreachStage.ongoing


def test_contact_log_advance_stage_opt_out(ctx):
    firm = _seed_firm(ctx, name="Stage Firm E", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Stage Partner E")

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 5),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="Historical backfill",
        advance_stage=False,
    )
    assert resp.stage_advanced is False
    assert resp.partner.outreach_stage == OutreachStage.researched


def test_contact_log_sets_next_touch_inline(ctx):
    firm = _seed_firm(ctx, name="Touch Firm", tier=FirmTier.primary)
    partner = PartnersService.upsert(ctx, firm.name, "Touch Partner")

    resp = ContactsService.log(
        ctx,
        firm_name=firm.name,
        partner_name=partner.name,
        contact_date=date(2026, 6, 10),
        channel=ContactChannel.call,
        initiated_by=InitiatedBy.me,
        summary="Catch-up call",
        next_touch_date=date(2026, 7, 1),
        next_touch_topic="Share the marketing-effectiveness piece",
    )
    assert resp.partner.next_touch_date == date(2026, 7, 1)
    assert resp.partner.next_touch_topic == "Share the marketing-effectiveness piece"


def test_planning_cadence_derives_due_touch(ctx):
    from src.repository import partners as partners_repo

    firm = _seed_firm(ctx, name="Cadence Primary", tier=FirmTier.primary)
    today = date.today()
    # 95d since contact: past the 90d ideal, below the 120d overdue threshold.
    p = PartnersService.upsert(ctx, firm.name, "Cadence Partner")
    partners_repo.update_partner_fields(
        ctx.conn, p.id, {"last_contact_date": today - timedelta(days=95)},
    )

    due = PlanningService.list_due_touches(ctx, window_days=14)
    row = next(d for d in due if d.partner_name == "Cadence Partner")
    assert row.status == "due_soon"
    assert row.due_source == "cadence"
    assert row.suggested_next_touch_date == today - timedelta(days=5)
    assert row.days_until_next_touch == -5


def test_planning_ned_tier_has_cadence_and_appears_in_all(ctx):
    from src.repository import partners as partners_repo

    firm = _seed_firm(ctx, name="NED Boutique", tier=FirmTier.ned)
    today = date.today()
    p = PartnersService.upsert(ctx, firm.name, "NED Gatekeeper")
    partners_repo.update_partner_fields(
        ctx.conn, p.id, {"last_contact_date": today - timedelta(days=200)},
    )

    due = PlanningService.list_due_touches(ctx, window_days=14)
    row = next(d for d in due if d.partner_name == "NED Gatekeeper")
    assert row.status == "overdue"
    assert row.tier == "ned"


def test_planning_missed_planned_touch_is_overdue(ctx):
    from src.repository import partners as partners_repo

    firm = _seed_firm(ctx, name="Missed Plan Firm", tier=FirmTier.primary)
    today = date.today()
    p = PartnersService.upsert(
        ctx, firm.name, "Missed Plan Partner",
        next_touch_date=today - timedelta(days=3),
    )
    partners_repo.update_partner_fields(
        ctx.conn, p.id, {"last_contact_date": today - timedelta(days=10)},
    )

    due = PlanningService.list_due_touches(ctx, window_days=14)
    row = next(d for d in due if d.partner_name == "Missed Plan Partner")
    assert row.status == "overdue"
    assert row.due_source == "planned"
    assert row.days_until_next_touch == -3


def test_planning_quarter_spacing_unique_weeks(ctx):
    for i in range(4):
        firm = _seed_firm(ctx, name=f"Primary {i}", tier=FirmTier.primary)
        PartnersService.upsert(ctx, firm.name, f"Partner {i}")

    plan = PlanningService.plan_quarter(ctx, year=2026, quarter=2)
    weeks = [s.week_starting for s in plan.slots]
    assert len(weeks) == len(set(weeks))
    assert len(plan.slots) == 4


def test_notes_create_updates_search_index(ctx):
    firm = _seed_firm(ctx, name="TML Notes", tier=FirmTier.specialist)
    note = NotesService.create(
        ctx, entity_type=NoteEntityType.firm, entity_ulid=firm.ulid,
        body="Marketing leadership specialist; primary entry route.",
    )
    hits = SearchService.search(ctx, query="marketing")
    assert any(h.entity_type == "note" and h.entity_ulid == note.ulid for h in hits)


def test_search_finds_firm_after_upsert(ctx):
    firm = _seed_firm(ctx, name="Distinctive Search Firm Beta",
                      tier=FirmTier.primary)
    FirmsService.update_notes(ctx, firm.ulid, "Specialist in Milanese exec search")
    hits = SearchService.search(ctx, query="Milanese")
    assert any(h.entity_ulid == firm.ulid for h in hits)


def _seed_for_export(ctx):
    firm = _seed_firm(ctx, name="TML Partners", tier=FirmTier.specialist,
                      region="London")
    FirmsService.update_state(ctx, firm.ulid, RelationshipState.warming)
    p = PartnersService.upsert(ctx, firm.name, "Imogen Carr",
                                title="Associate Partner")
    ContactsService.log(
        ctx, firm_name=firm.name, partner_name=p.name,
        contact_date=date(2026, 5, 2), channel=ContactChannel.email,
        initiated_by=InitiatedBy.me, summary="Market-mapping discussion",
        value_given="Shared notes",
    )


def test_export_then_import_round_trip(ctx, db):
    _seed_for_export(ctx)
    md = ExportService.export_to_markdown(ctx)

    # Fresh DB to import into.
    import sqlite3
    from pathlib import Path
    fresh = sqlite3.connect(":memory:", isolation_level=None)
    fresh.row_factory = sqlite3.Row
    fresh.execute("PRAGMA foreign_keys = ON")
    for m in sorted(Path("migrations").glob("*.sql")):
        fresh.executescript(m.read_text())
    ctx2 = ServiceContext(conn=fresh, actor="FF", transport="system")
    summary = ImportService.import_markdown(ctx2, md)
    assert summary.firms_created == 1
    assert summary.partners_created == 1
    assert summary.contacts_imported == 1

    md2 = ExportService.export_to_markdown(ctx2)
    assert md.strip() == md2.strip()


def test_import_is_idempotent(ctx):
    _seed_for_export(ctx)
    md = ExportService.export_to_markdown(ctx)

    import sqlite3
    from pathlib import Path
    fresh = sqlite3.connect(":memory:", isolation_level=None)
    fresh.row_factory = sqlite3.Row
    fresh.execute("PRAGMA foreign_keys = ON")
    for m in sorted(Path("migrations").glob("*.sql")):
        fresh.executescript(m.read_text())
    ctx2 = ServiceContext(conn=fresh, actor="FF", transport="system")

    s1 = ImportService.import_markdown(ctx2, md)
    s2 = ImportService.import_markdown(ctx2, md)
    assert s1.contacts_imported == 1
    assert s2.contacts_imported == 0
    assert s2.contacts_skipped >= 1
    assert s2.firms_created == 0
    assert s2.partners_created == 0
