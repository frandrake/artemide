"""Repository smoke tests — one per module."""
from __future__ import annotations

import time
from datetime import date

from src.models import (
    AuditAction,
    AuditTransport,
    CalendarStatus,
    ContactChannel,
    FirmTier,
    InitiatedBy,
    NoteEntityType,
    RelationshipState,
)
from src.repository import (
    audit_log,
    calendar,
    contacts,
    firms,
    notes,
    partners,
    search_index,
)


def test_firms_crud_and_soft_delete(db):
    firm = firms.insert_firm(db, name="TML Partners", tier=FirmTier.specialist, region="London")
    assert firm.ulid and len(firm.ulid) == 26

    fetched = firms.get_firm_by_ulid(db, firm.ulid)
    assert fetched is not None and fetched.name == "TML Partners"

    listed = firms.list_firms(db, tier=FirmTier.specialist)
    assert len(listed) == 1

    firms.soft_delete_firm(db, firm.id)
    assert firms.list_firms(db) == []
    assert len(firms.list_firms(db, include_deleted=True)) == 1

    firms.restore_firm(db, firm.id)
    assert len(firms.list_firms(db)) == 1


def test_partners_upsert_and_updated_at_trigger(db):
    firm = firms.insert_firm(db, name="Spencer Stuart", tier=FirmTier.primary, region="Global")
    p = partners.insert_partner(db, firm_id=firm.id, name="Sarah Whitfield", title="Partner")
    assert p.firm_id == firm.id

    by_name = partners.get_partner_by_name(db, firm.id, "Sarah Whitfield")
    assert by_name is not None and by_name.ulid == p.ulid

    before_updated_at = p.updated_at
    time.sleep(1.05)
    updated = partners.update_partner_fields(db, p.id, {"title": "Consultant"})
    assert updated is not None
    assert updated.updated_at > before_updated_at


def test_contacts_insert_list_and_duplicate(db):
    firm = firms.insert_firm(db, name="Egon Zehnder", tier=FirmTier.primary)
    p = partners.insert_partner(db, firm_id=firm.id, name="Elena Brescia")

    contact_date = date(2026, 5, 2)
    contacts.insert_contact(
        db,
        partner_id=p.id,
        contact_date=contact_date,
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="Intro note",
    )
    listed = contacts.list_contacts_by_partner(db, p.id)
    assert len(listed) == 1
    assert contacts.is_duplicate_contact(db, p.id, contact_date, ContactChannel.email) is True
    assert contacts.is_duplicate_contact(db, p.id, contact_date, ContactChannel.call) is False


def test_notes_insert_and_list(db):
    firm = firms.insert_firm(db, name="Korn Ferry", tier=FirmTier.primary)
    note = notes.insert_note(
        db,
        entity_type=NoteEntityType.firm,
        entity_id=firm.ulid,
        body="Background research summary.",
    )
    fetched = notes.get_note_by_ulid(db, note.ulid)
    assert fetched is not None and fetched.body.startswith("Background")

    listed = notes.list_notes_by_entity(db, NoteEntityType.firm, firm.ulid)
    assert len(listed) == 1


def test_quarter_topic_upsert_and_update(db):
    q = calendar.upsert_quarter_topic(db, year=2026, quarter=2, topic="Agentic CMO themes")
    assert q.status == CalendarStatus.planned

    fetched = calendar.get_quarter_topic(db, year=2026, quarter=2)
    assert fetched is not None and fetched.topic == "Agentic CMO themes"

    updated = calendar.upsert_quarter_topic(
        db, year=2026, quarter=2, topic="Agentic CMO themes — v2", status=CalendarStatus.in_progress
    )
    assert updated.topic.endswith("v2")
    assert updated.status == CalendarStatus.in_progress

    listed = calendar.list_quarter_topics(db, 2026)
    assert len(listed) == 1


def test_audit_log_insert_and_list(db):
    firm = firms.insert_firm(db, name="Heidrick & Struggles", tier=FirmTier.primary)
    entry = audit_log.insert_audit_entry(
        db,
        entity_type="firm",
        entity_id=firm.ulid,
        action=AuditAction.create,
        actor="francesco",
        transport=AuditTransport.cli,
        payload='{"name":"Heidrick & Struggles"}',
    )
    assert entry.ulid and len(entry.ulid) == 26

    by_entity = audit_log.list_audit_entries_by_entity(db, "firm", firm.ulid)
    assert len(by_entity) == 1

    recent = audit_log.list_recent_audit_entries(db)
    assert recent[0].ulid == entry.ulid


def test_search_index_upsert_and_query(db):
    firm = firms.insert_firm(db, name="Russell Reynolds", tier=FirmTier.primary)
    search_index.upsert_search_row(
        db,
        entity_type="firm",
        entity_ulid=firm.ulid,
        primary_text="Russell Reynolds",
        secondary_text="Global executive search firm",
    )
    hits = search_index.search(db, query="Reynolds")
    assert len(hits) == 1 and hits[0]["entity_ulid"] == firm.ulid

    search_index.delete_search_row(db, entity_type="firm", entity_ulid=firm.ulid)
    assert search_index.search(db, query="Reynolds") == []
