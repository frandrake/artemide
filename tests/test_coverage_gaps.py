"""Targeted tests for service + route paths not exercised elsewhere.

The aim here is to keep the ≥80% coverage gate on src/services and
src/api honest; the substantive behaviour these flows describe is
already covered in test_services and test_api.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("ARTEMIDE_API_TOKEN", "test-token")
os.environ.setdefault("ARTEMIDE_COOKIE_SECRET", "test-cookie-secret")
os.environ.setdefault("ARTEMIDE_COOKIE_SECURE", "false")
os.environ.setdefault("ARTEMIDE_COOKIE_DOMAIN", "")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.deps import get_db  # noqa: E402
from src.app import app  # noqa: E402
from src.models import (  # noqa: E402
    ContactChannel, FirmTier, InitiatedBy, NoteEntityType, RelationshipState,
)
from src.repository import firms as firms_repo  # noqa: E402
from src.services import ServiceContext  # noqa: E402
from src.services.contacts_service import ContactsService  # noqa: E402
from src.services.exceptions import NotFoundError  # noqa: E402
from src.services.export_service import ExportService  # noqa: E402
from src.services.firms_service import FirmsService  # noqa: E402
from src.services.notes_service import NotesService  # noqa: E402
from src.services.partners_service import PartnersService  # noqa: E402
from src.services.search_service import SearchService  # noqa: E402


# ---------- fixture: real DB file so TestClient lifespan is happy ----------

@pytest.fixture
def db_file(tmp_path, monkeypatch):
    p = tmp_path / "artemide.db"
    monkeypatch.setenv("ARTEMIDE_DB_PATH", str(p))
    from src.db import init_db
    init_db(str(p))
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


# ---------- partners_service: delete/restore/planned-touch/follow-ups ----------

def test_partners_delete_restore_planned_touch_followups(db_file):
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    firms_repo.insert_firm(db_file, name="TML", tier=FirmTier.specialist)
    p = PartnersService.upsert(ctx, "TML", "Imogen", title="AP")

    updated = PartnersService.update_planned_touch(
        ctx, p.ulid, date(2026, 6, 1), "PoV share"
    )
    assert updated.next_touch_topic == "PoV share"

    with_followups = PartnersService.update_follow_ups(
        ctx, p.ulid, ["mapping deck by Friday", "intro to peer"]
    )
    assert "mapping deck" in (with_followups.follow_ups_outstanding or "")

    cleared = PartnersService.update_follow_ups(ctx, p.ulid, [])
    assert cleared.follow_ups_outstanding is None

    PartnersService.soft_delete(ctx, p.ulid)
    listed = PartnersService.list_by_firm(ctx, firms_repo.get_firm_by_name(db_file, "TML").ulid)
    assert all(x.ulid != p.ulid for x in listed)

    PartnersService.restore(ctx, p.ulid)
    listed_again = PartnersService.list_by_firm(ctx, firms_repo.get_firm_by_name(db_file, "TML").ulid)
    assert any(x.ulid == p.ulid for x in listed_again)


def test_partners_get_by_name_not_found_raises(db_file):
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    with pytest.raises(NotFoundError):
        PartnersService.get_by_name(ctx, "Nope Co", "Nobody")


# ---------- firms_service: soft delete + restore + update_notes path ----------

def test_firms_soft_delete_restore_and_update_notes(db_file):
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    firms_repo.insert_firm(db_file, name="Russell Reynolds", tier=FirmTier.primary)
    firm = FirmsService.get_by_name(ctx, "Russell Reynolds")

    FirmsService.update_notes(ctx, firm.ulid, "Tech overweight; transformation-anchored.")
    refreshed = FirmsService.get_by_ulid(ctx, firm.ulid)
    assert refreshed.notes_summary.startswith("Tech")

    FirmsService.soft_delete(ctx, firm.ulid)
    assert FirmsService.list(ctx) == []
    FirmsService.restore(ctx, firm.ulid)
    assert len(FirmsService.list(ctx)) == 1


# ---------- search_service.rebuild_index ----------

def test_search_rebuild_repopulates_index(db_file):
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    firm = firms_repo.insert_firm(db_file, name="True Search", tier=FirmTier.specialist)
    p = PartnersService.upsert(ctx, firm.name, "Trace", title="Partner")
    ContactsService.log(
        ctx, firm_name=firm.name, partner_name="Trace",
        contact_date=date(2026, 5, 1), channel=ContactChannel.email,
        initiated_by=InitiatedBy.me, summary="Cold intro pitch",
    )
    NotesService.create(ctx, entity_type=NoteEntityType.firm, entity_ulid=firm.ulid,
                        body="Enterprise SaaS focus.")

    db_file.execute("DELETE FROM search_index")
    count = SearchService.rebuild_index(ctx)
    assert count >= 4  # firm + partner + contact + note

    hits = SearchService.search(ctx, query="SaaS")
    assert any(h.entity_type == "note" for h in hits)

    typed = SearchService.search(ctx, query="Trace", entity_type="partner")
    assert all(h.entity_type == "partner" for h in typed)

    # Empty query short-circuits.
    assert SearchService.search(ctx, query="   ") == []


# ---------- export_service: CSV per entity type ----------

def test_export_csv_supports_all_three_entity_types(db_file):
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    firm = firms_repo.insert_firm(db_file, name="Korn Ferry", tier=FirmTier.primary)
    p = PartnersService.upsert(ctx, firm.name, "Test", title="Partner")
    ContactsService.log(
        ctx, firm_name=firm.name, partner_name=p.name,
        contact_date=date(2026, 5, 2), channel=ContactChannel.call,
        initiated_by=InitiatedBy.me, summary="Comp benchmarking",
    )
    for kind in ("firm", "partner", "contact"):
        out = ExportService.export_to_csv(ctx, kind)
        assert "ulid" in out.splitlines()[0]
    with pytest.raises(ValueError):
        ExportService.export_to_csv(ctx, "bogus")


# ---------- routes_system: /api/v1/system/info ----------

def test_system_info_endpoint_returns_expected_shape(db_file):
    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            r = c.get("/api/v1/system/info", headers={"Authorization": "Bearer test-token"})
            assert r.status_code == 200, r.text
            body = r.json()
            for k in (
                "schema_version", "schema_applied_at", "build_hash",
                "token_source", "counts", "dependencies",
            ):
                assert k in body
            assert isinstance(body["counts"], dict)
    finally:
        app.dependency_overrides.clear()


# ---------- routes_admin: rotate-token + list backups ----------

def test_admin_rotate_token_invalidates_old(db_file):
    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            r = c.post("/api/v1/admin/rotate-token", headers={"Authorization": "Bearer test-token"})
            assert r.status_code == 200, r.text
            new_token = r.json()["new_token"]
            assert len(new_token) >= 40

            # old token rejected
            old = c.get("/api/v1/firms", headers={"Authorization": "Bearer test-token"})
            assert old.status_code == 401
            # new token accepted
            ok = c.get("/api/v1/firms", headers={"Authorization": f"Bearer {new_token}"})
            assert ok.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_admin_list_backups_empty_dir(tmp_path, monkeypatch, db_file):
    monkeypatch.setenv("ARTEMIDE_BACKUP_DIR", str(tmp_path / "absent"))
    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            r = c.get("/api/v1/admin/backups", headers={"Authorization": "Bearer test-token"})
            assert r.status_code == 200
            assert r.json() == {"backups": []}
    finally:
        app.dependency_overrides.clear()


# ---------- routes_partners: PATCH planned-touch + follow-ups + delete + restore ----------

def test_partner_patch_and_lifecycle_via_rest(db_file):
    firms_repo.insert_firm(db_file, name="Egon Zehnder", tier=FirmTier.primary)
    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            h = {"Authorization": "Bearer test-token"}
            created = c.post("/api/v1/partners", json={
                "firm_name": "Egon Zehnder", "name": "Elena", "title": "Partner",
            }, headers=h).json()
            ulid = created["ulid"]

            patched = c.patch(f"/api/v1/partners/{ulid}",
                              json={"next_planned_touch_date": "2026-07-01",
                                    "next_planned_topic": "NED track",
                                    "follow_ups_outstanding": ["resend deck"]}, headers=h)
            assert patched.status_code == 200, patched.text
            body = patched.json()
            assert body["next_touch_topic"] == "NED track"
            assert "resend deck" in (body["follow_ups_outstanding"] or "")

            r = c.delete(f"/api/v1/partners/{ulid}", headers=h)
            assert r.status_code == 204
            r2 = c.post(f"/api/v1/partners/{ulid}/restore", headers=h)
            assert r2.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------- routes_firms: PATCH + soft delete + restore ----------

def test_firm_patch_state_via_rest(db_file):
    firms_repo.insert_firm(db_file, name="Heidrick & Struggles", tier=FirmTier.primary)
    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            h = {"Authorization": "Bearer test-token"}
            firm = c.get("/api/v1/firms", headers=h).json()[0]
            ulid = firm["ulid"]

            # legal transition: cold → warming
            r = c.patch(f"/api/v1/firms/{ulid}",
                        json={"relationship_state": "warming", "notes": "Updated"}, headers=h)
            assert r.status_code == 200
            body = r.json()
            assert body["relationship_state"] == "warming"
            assert body["notes_summary"] == "Updated"

            del_r = c.delete(f"/api/v1/firms/{ulid}", headers=h)
            assert del_r.status_code == 204
            res_r = c.post(f"/api/v1/firms/{ulid}/restore", headers=h)
            assert res_r.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------- routes_planning: /quarter and /due-touches + quarter-topic ----------

def test_planning_endpoints_round_trip(db_file):
    firm = firms_repo.insert_firm(db_file, name="Spencer Stuart", tier=FirmTier.primary)
    ctx = ServiceContext(conn=db_file, actor="FF", transport="cli")
    PartnersService.upsert(ctx, firm.name, "Sarah", title="Partner")

    app.dependency_overrides[get_db] = lambda: (yield db_file)
    try:
        with TestClient(app) as c:
            h = {"Authorization": "Bearer test-token"}
            r = c.post("/api/v1/planning/quarter-topic",
                       json={"year": 2026, "quarter": 2, "topic": "Test topic"}, headers=h)
            assert r.status_code == 200

            q = c.get("/api/v1/planning/quarter?year=2026&quarter=2", headers=h).json()
            assert q["topic"] == "Test topic"
            assert isinstance(q["slots"], list)

            due = c.get("/api/v1/planning/due-touches?window_days=30&tier=primary", headers=h)
            assert due.status_code == 200
    finally:
        app.dependency_overrides.clear()
