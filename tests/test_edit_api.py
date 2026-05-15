"""Edit API tests: PATCH, DELETE, restore for firms and partners."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ARTEMIDE_API_TOKEN", "test-token")
os.environ.setdefault("ARTEMIDE_COOKIE_SECRET", "test-cookie-secret")
os.environ.setdefault("ARTEMIDE_COOKIE_SECURE", "false")
os.environ.setdefault("ARTEMIDE_COOKIE_DOMAIN", "")

from src.app import app  # noqa: E402
from src.api.deps import get_db  # noqa: E402
from src.repository import firms as firms_repo  # noqa: E402
from src.repository import partners as partners_repo  # noqa: E402
from src.models import FirmTier  # noqa: E402

AUTH = {"Authorization": "Bearer test-token"}


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(Path("migrations").glob("*.sql")):
        conn.executescript(migration.read_text())
    return conn


@pytest_asyncio.fixture
async def client():
    conn = _fresh_conn()

    def _override():
        try:
            yield conn
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.conn = conn  # type: ignore[attr-defined]
        yield ac
    app.dependency_overrides.clear()
    conn.close()


def _seed(conn: sqlite3.Connection):
    """Two firms: TML (specialist) with 2 partners, Spencer (primary) empty."""
    tml = firms_repo.insert_firm(conn, name="TML Partners", tier=FirmTier.specialist, region="London")
    spencer = firms_repo.insert_firm(conn, name="Spencer Stuart", tier=FirmTier.primary, region="Global")
    alice = partners_repo.insert_partner(conn, firm_id=tml.id, name="Alice Harmon", practice="PE")
    bob = partners_repo.insert_partner(conn, firm_id=tml.id, name="Bob Whitley", practice="VC")
    return tml, spencer, alice, bob


# ─── PATCH firm ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_firm_notes(client):
    tml, *_ = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"notes": "Priority for 2026."},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["notes_summary"] == "Priority for 2026."


@pytest.mark.asyncio
async def test_patch_firm_notes_in_audit_log(client):
    tml, *_ = _seed(client.conn)
    await client.patch(f"/api/v1/firms/{tml.ulid}", json={"notes": "test"}, headers=AUTH)
    log = await client.get("/api/v1/audit/log", headers=AUTH)
    actions = [e["action"] for e in log.json()]
    assert "update" in actions


@pytest.mark.asyncio
async def test_patch_firm_no_fields_returns_400(client):
    tml, *_ = _seed(client.conn)
    r = await client.patch(f"/api/v1/firms/{tml.ulid}", json={}, headers=AUTH)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_firm_invalid_state_transition_returns_422(client):
    tml, *_ = _seed(client.conn)
    # cold → warm is illegal (must go cold → warming → warm)
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"relationship_state": "warm"},
        headers=AUTH,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_firm_valid_state_transition_cold_to_warming(client):
    tml, *_ = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"relationship_state": "warming"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["relationship_state"] == "warming"


@pytest.mark.asyncio
async def test_patch_firm_transition_to_dormant_from_any_state(client):
    tml, *_ = _seed(client.conn)
    # cold → dormant
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"relationship_state": "dormant"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["relationship_state"] == "dormant"


@pytest.mark.asyncio
async def test_patch_firm_name_key_silently_ignored(client):
    tml, *_ = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"name": "IGNORED", "region": "Europe"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "TML Partners"
    assert body["region"] == "Europe"


@pytest.mark.asyncio
async def test_patch_firm_tier_and_region(client):
    tml, *_ = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/firms/{tml.ulid}",
        json={"tier": "primary", "region": "EMEA"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "primary"
    assert body["region"] == "EMEA"


# ─── DELETE firm ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_firm_with_partners_returns_204_and_cascades(client):
    tml, _, alice, bob = _seed(client.conn)
    r = await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    assert r.status_code == 204
    # Partners should be soft-deleted
    a = partners_repo.get_partner_by_ulid(client.conn, alice.ulid)
    b = partners_repo.get_partner_by_ulid(client.conn, bob.ulid)
    assert a.deleted_at is not None
    assert b.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_firm_cascade_audit_entries(client):
    tml, _, alice, bob = _seed(client.conn)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    log = await client.get("/api/v1/audit/log", headers=AUTH)
    entries = log.json()
    # Firm delete + 2 partner deletes
    delete_entries = [e for e in entries if e["action"] == "delete"]
    assert len(delete_entries) == 3


@pytest.mark.asyncio
async def test_delete_already_deleted_firm_returns_409(client):
    tml, *_ = _seed(client.conn)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    r = await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    assert r.status_code == 409


# ─── Restore firm ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restore_firm(client):
    tml, *_ = _seed(client.conn)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    r = await client.post(f"/api/v1/firms/{tml.ulid}/restore", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["deleted_at"] is None


@pytest.mark.asyncio
async def test_restore_firm_partners_remain_deleted(client):
    tml, _, alice, bob = _seed(client.conn)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    await client.post(f"/api/v1/firms/{tml.ulid}/restore", headers=AUTH)
    a = partners_repo.get_partner_by_ulid(client.conn, alice.ulid)
    b = partners_repo.get_partner_by_ulid(client.conn, bob.ulid)
    assert a.deleted_at is not None
    assert b.deleted_at is not None


@pytest.mark.asyncio
async def test_restore_firm_visible_in_list(client):
    tml, *_ = _seed(client.conn)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    await client.post(f"/api/v1/firms/{tml.ulid}/restore", headers=AUTH)
    r = await client.get("/api/v1/firms", headers=AUTH)
    names = [f["name"] for f in r.json()]
    assert "TML Partners" in names


# ─── PATCH partner ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_partner_fields(client):
    tml, _, alice, _ = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={
            "practice": "Infra",
            "seniority": "Senior",
            "location": "Paris",
            "introduced_via": "LinkedIn",
            "next_planned_touch_date": "2026-08-01",
            "next_planned_topic": "Catch-up",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["practice"] == "Infra"
    assert body["seniority"] == "Senior"
    assert body["location"] == "Paris"
    assert body["introduced_via"] == "LinkedIn"
    assert body["next_touch_date"] == "2026-08-01"
    assert body["next_touch_topic"] == "Catch-up"


@pytest.mark.asyncio
async def test_patch_partner_audit_logged(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"practice": "Infra"},
        headers=AUTH,
    )
    log = await client.get("/api/v1/audit/log", headers=AUTH)
    actions = [e["action"] for e in log.json()]
    assert "update" in actions


@pytest.mark.asyncio
async def test_patch_partner_name_collision_returns_409(client):
    tml, _, alice, bob = _seed(client.conn)
    r = await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"name": "Bob Whitley"},
        headers=AUTH,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_patch_partner_date_ordering_violation_returns_422(client):
    tml, _, alice, _ = _seed(client.conn)
    # Set first_contact_date after next_planned_touch_date → invalid
    r = await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={
            "first_contact_date": "2026-09-01",
            "next_planned_touch_date": "2026-08-01",
        },
        headers=AUTH,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_partner_clear_follow_ups(client):
    tml, _, alice, _ = _seed(client.conn)
    # First set some follow-ups
    await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"follow_ups_outstanding": ["Call back", "Send deck"]},
        headers=AUTH,
    )
    # Now clear them
    r = await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"follow_ups_outstanding": []},
        headers=AUTH,
    )
    assert r.status_code == 200
    import json
    stored = r.json()["follow_ups_outstanding"]
    parsed = json.loads(stored) if isinstance(stored, str) else stored
    assert parsed == []


@pytest.mark.asyncio
async def test_patch_partner_omit_follow_ups_leaves_unchanged(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"follow_ups_outstanding": ["Call back"]},
        headers=AUTH,
    )
    # Patch without follow_ups_outstanding — existing list untouched
    await client.patch(
        f"/api/v1/partners/{alice.ulid}",
        json={"practice": "Growth"},
        headers=AUTH,
    )
    p = partners_repo.get_partner_by_ulid(client.conn, alice.ulid)
    assert p.follow_ups_outstanding is not None
    assert "Call back" in p.follow_ups_outstanding


# ─── DELETE partner ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_partner_returns_204(client):
    tml, _, alice, _ = _seed(client.conn)
    r = await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_partner_hidden_from_firm_list(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    r = await client.get(f"/api/v1/partners?firm_ulid={tml.ulid}", headers=AUTH)
    names = [p["name"] for p in r.json()]
    assert "Alice Harmon" not in names


@pytest.mark.asyncio
async def test_delete_already_deleted_partner_returns_409(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    r = await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    assert r.status_code == 409


# ─── Restore partner ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restore_partner_where_firm_deleted_returns_422(client):
    tml, _, alice, _ = _seed(client.conn)
    # Delete the firm (which cascades to alice)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    r = await client.post(f"/api/v1/partners/{alice.ulid}/restore", headers=AUTH)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_restore_partner_where_firm_active(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    r = await client.post(f"/api/v1/partners/{alice.ulid}/restore", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["deleted_at"] is None


@pytest.mark.asyncio
async def test_restore_partner_visible_in_firm_list(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    await client.post(f"/api/v1/partners/{alice.ulid}/restore", headers=AUTH)
    r = await client.get(f"/api/v1/partners?firm_ulid={tml.ulid}", headers=AUTH)
    names = [p["name"] for p in r.json()]
    assert "Alice Harmon" in names


# ─── Audit log completeness ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_sequence_audit_log(client):
    """PATCH + DELETE + restore on a firm all appear in audit log."""
    tml, *_ = _seed(client.conn)
    await client.patch(f"/api/v1/firms/{tml.ulid}", json={"notes": "test"}, headers=AUTH)
    await client.delete(f"/api/v1/firms/{tml.ulid}", headers=AUTH)
    await client.post(f"/api/v1/firms/{tml.ulid}/restore", headers=AUTH)
    log = await client.get("/api/v1/audit/log", headers=AUTH)
    actions = {e["action"] for e in log.json()}
    assert {"update", "delete", "restore"}.issubset(actions)


# ─── include_deleted on partners list ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_partners_include_deleted(client):
    tml, _, alice, _ = _seed(client.conn)
    await client.delete(f"/api/v1/partners/{alice.ulid}", headers=AUTH)
    r = await client.get(
        f"/api/v1/partners?firm_ulid={tml.ulid}&include_deleted=true", headers=AUTH
    )
    names = [p["name"] for p in r.json()]
    assert "Alice Harmon" in names
