from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from src.repository import intake_previews as previews_repo
from src.services import ServiceContext
from src.services.exceptions import ConflictError, ForbiddenRoleError, NotFoundError, ValidationError
from src.services.intake_service import IntakeService
from src.services.person_identity_service import PersonIdentityService


def _ctx(db: sqlite3.Connection, *, role: str = "owner") -> ServiceContext:
    return ServiceContext(conn=db, actor="tester", transport="system", role=role)  # type: ignore[arg-type]


def _insert_partner(db: sqlite3.Connection, *, name: str = "Alex Morgan") -> str:
    firm_ulid = "01J00000000000000000000001"
    partner_ulid = "01J00000000000000000000002"
    db.execute(
        "INSERT INTO firms (ulid, name, tier) VALUES (?, ?, 'primary')",
        (firm_ulid, f"Firm {name}"),
    )
    firm_id = db.execute("SELECT id FROM firms WHERE ulid = ?", (firm_ulid,)).fetchone()[0]
    db.execute(
        "INSERT INTO partners (ulid, firm_id, name) VALUES (?, ?, ?)",
        (partner_ulid, firm_id, name),
    )
    return partner_ulid


def _insert_board_contact(db: sqlite3.Connection, *, name: str = "Alex Morgan") -> str:
    ulid = "01J00000000000000000000003"
    db.execute("INSERT INTO board_contact (ulid, name) VALUES (?, ?)", (ulid, name))
    return ulid


def _preview_kwargs() -> dict:
    source_input = b"public role announcement"
    return {
        "proposed_payload": {"organisation": "Example plc", "role_title": "CMO"},
        "provider": "example-provider",
        "model": "example-model",
        "prompt": "Extract only facts supported by the supplied public sources.",
        "input_hash": hashlib.sha256(source_input).hexdigest(),
        "sources": [{"url": "https://example.test/role", "label": "Role announcement"}],
        "provenance": {"retrieved_at": "2026-07-21T10:00:00Z"},
    }


def test_migration_creates_neutral_identity_and_physically_separate_preview_tables(db):
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert {
        "person_identity",
        "executive_person_link",
        "board_person_link",
        "executive_ai_intake_preview",
        "board_ai_intake_preview",
    } <= tables

    identity_columns = {
        row[1] for row in db.execute("PRAGMA table_info(person_identity)").fetchall()
    }
    assert not identity_columns.intersection(
        {"relationship", "relationship_state", "notes", "notes_summary", "last_contact_date"}
    )

    executive_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='executive_ai_intake_preview'"
    ).fetchone()[0]
    board_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='board_ai_intake_preview'"
    ).fetchone()[0]
    assert "workstream" not in executive_sql.lower()
    assert "workstream" not in board_sql.lower()


def test_identity_links_are_explicit_owner_only_and_never_created_by_name(db):
    partner_ulid = _insert_partner(db)
    board_contact_ulid = _insert_board_contact(db)
    owner = _ctx(db)

    person = PersonIdentityService.create(
        owner,
        display_name="Alex Morgan",
        email="alex@example.test",
        linkedin_url="https://linkedin.test/in/alex",
    )
    links = PersonIdentityService.get_links(owner, person["ulid"])
    assert links == {"partner_ulids": [], "board_contact_ulids": []}

    PersonIdentityService.link_partner(owner, person["ulid"], partner_ulid)
    PersonIdentityService.link_board_contact(owner, person["ulid"], board_contact_ulid)
    assert PersonIdentityService.get_links(owner, person["ulid"]) == {
        "partner_ulids": [partner_ulid],
        "board_contact_ulids": [board_contact_ulid],
    }

    neutral = PersonIdentityService.get_by_ulid(owner, person["ulid"])
    assert "relationship" not in neutral
    assert "relationship_state" not in neutral
    assert "notes" not in neutral

    with pytest.raises(ForbiddenRoleError):
        PersonIdentityService.get_links(_ctx(db, role="bot"), person["ulid"])


def test_identity_link_rejects_missing_targets_and_duplicate_ownership(db):
    partner_ulid = _insert_partner(db)
    owner = _ctx(db)
    first = PersonIdentityService.create(owner, display_name="First")
    second = PersonIdentityService.create(owner, display_name="Second")

    with pytest.raises(NotFoundError):
        PersonIdentityService.link_partner(owner, first["ulid"], "01J00000000000000000000009")

    PersonIdentityService.link_partner(owner, first["ulid"], partner_ulid)
    with pytest.raises(ConflictError):
        PersonIdentityService.link_partner(owner, second["ulid"], partner_ulid)


def test_preview_lifecycle_is_owner_only_and_confirmation_is_preview_only(db):
    owner = _ctx(db)
    before_engagements = db.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    preview = IntakeService.create_executive_preview(owner, **_preview_kwargs())

    assert preview["status"] == "draft"
    assert preview["proposed_payload"]["organisation"] == "Example plc"
    assert previews_repo.get_executive_preview_by_ulid(db, preview["ulid"])["status"] == "draft"

    confirmed = IntakeService.confirm_executive_preview(
        owner,
        preview["ulid"],
        corrected_payload={"organisation": "Example PLC", "role_title": "Chief Marketing Officer"},
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["corrected_payload"]["organisation"] == "Example PLC"
    assert confirmed["confirmed_at"] is not None
    assert confirmed["confirmed_by"] == "tester"
    assert db.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == before_engagements

    with pytest.raises(ConflictError):
        IntakeService.reject_executive_preview(owner, preview["ulid"], reason="changed mind")
    with pytest.raises(ForbiddenRoleError):
        IntakeService.get_executive_preview(_ctx(db, role="bot"), preview["ulid"])


def test_board_preview_is_separate_rejectable_and_emits_no_outbox_or_search(db):
    owner = _ctx(db)
    before_outbox = db.execute("SELECT COUNT(*) FROM events_outbox").fetchone()[0]
    before_search = db.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
    before_opportunities = db.execute("SELECT COUNT(*) FROM board_opportunity").fetchone()[0]

    preview = IntakeService.create_board_preview(
        owner,
        **{
            **_preview_kwargs(),
            "proposed_payload": {"organisation": "Example plc", "role": "ned"},
        },
    )
    rejected = IntakeService.reject_board_preview(owner, preview["ulid"], reason="Insufficient provenance")

    assert rejected["status"] == "rejected"
    assert rejected["rejected_at"] is not None
    assert rejected["rejected_by"] == "tester"
    assert rejected["rejection_reason"] == "Insufficient provenance"
    assert previews_repo.get_executive_preview_by_ulid(db, preview["ulid"]) is None
    assert db.execute("SELECT COUNT(*) FROM events_outbox").fetchone()[0] == before_outbox
    assert db.execute("SELECT COUNT(*) FROM search_index").fetchone()[0] == before_search
    assert db.execute("SELECT COUNT(*) FROM board_opportunity").fetchone()[0] == before_opportunities


def test_preview_validates_json_provenance_hash_and_state(db):
    owner = _ctx(db)
    bad = _preview_kwargs()
    bad["input_hash"] = "not-a-sha256"
    with pytest.raises(ValidationError):
        IntakeService.create_executive_preview(owner, **bad)

    bad = _preview_kwargs()
    bad["sources"] = []
    with pytest.raises(ValidationError):
        IntakeService.create_executive_preview(owner, **bad)

    bad = _preview_kwargs()
    bad["proposed_payload"] = {"unsupported": {"not", "json"}}
    with pytest.raises(ValidationError):
        IntakeService.create_executive_preview(owner, **bad)

    preview = IntakeService.create_executive_preview(owner, **_preview_kwargs())
    with pytest.raises(ValidationError):
        IntakeService.confirm_executive_preview(owner, preview["ulid"], corrected_payload=[])

    raw = db.execute(
        "SELECT proposed_payload, sources, provenance FROM executive_ai_intake_preview WHERE ulid = ?",
        (preview["ulid"],),
    ).fetchone()
    assert json.loads(raw["proposed_payload"])["organisation"] == "Example plc"
    assert isinstance(json.loads(raw["sources"]), list)
    assert isinstance(json.loads(raw["provenance"]), dict)
