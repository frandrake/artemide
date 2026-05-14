"""HTTP-level tests for the FastAPI app."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Pin env vars BEFORE importing the app so behaviour is identical in
# bare pytest and inside the container (where .env populates real values).
os.environ["ARTEMIDE_API_TOKEN"] = "test-token"
os.environ["ARTEMIDE_COOKIE_SECRET"] = "test-cookie-secret"
os.environ["ARTEMIDE_COOKIE_SECURE"] = "false"
os.environ["ARTEMIDE_COOKIE_DOMAIN"] = ""

from src.app import app  # noqa: E402
from src.api.deps import get_db  # noqa: E402
from src.models import FirmTier  # noqa: E402
from src.repository import firms as firms_repo  # noqa: E402


def _fresh_conn() -> sqlite3.Connection:
    # check_same_thread=False because FastAPI runs sync endpoints in a
    # worker threadpool; the in-memory connection from the test thread
    # must be usable from those workers too.
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(Path("migrations").glob("*.sql")):
        conn.executescript(migration.read_text())
    return conn


@pytest_asyncio.fixture
async def client(monkeypatch):
    conn = _fresh_conn()
    # Override get_db to yield this shared connection so the test setup
    # and the request handlers see the same in-memory database.
    def _override_get_db():
        try:
            yield conn
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.conn = conn  # type: ignore[attr-defined]
        yield ac
    app.dependency_overrides.clear()
    conn.close()


def _seed_firms(conn: sqlite3.Connection) -> None:
    firms_repo.insert_firm(conn, name="TML Partners", tier=FirmTier.specialist, region="London")
    firms_repo.insert_firm(conn, name="Spencer Stuart", tier=FirmTier.primary, region="Global")


# ---------- public + auth ----------

@pytest.mark.asyncio
async def test_health_no_auth(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    r = await client.get("/api/v1/firms")
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}


@pytest.mark.asyncio
async def test_login_with_wrong_token_returns_401(client):
    r = await client.post("/login", json={"token": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_sets_cookie_and_subsequent_request_succeeds(client):
    r = await client.post("/login", json={"token": "test-token"})
    assert r.status_code == 204
    assert "artemide_session" in [c.name for c in client.cookies.jar]

    r2 = await client.get("/api/v1/firms")
    assert r2.status_code == 200


# ---------- firms ----------

@pytest.mark.asyncio
async def test_list_firms_returns_seeded(client):
    _seed_firms(client.conn)
    r = await client.get(
        "/api/v1/firms", headers={"Authorization": "Bearer test-token"}
    )
    assert r.status_code == 200
    body = r.json()
    names = sorted(f["name"] for f in body)
    assert names == ["Spencer Stuart", "TML Partners"]
    assert all("id" not in f for f in body)


# ---------- partners + idempotency ----------

@pytest.mark.asyncio
async def test_partner_upsert_idempotency(client):
    _seed_firms(client.conn)
    headers = {
        "Authorization": "Bearer test-token",
        "Idempotency-Key": "abc-123",
    }
    payload = {"firm_name": "TML Partners", "name": "Imogen Carr", "title": "Associate Partner"}
    r1 = await client.post("/api/v1/partners", json=payload, headers=headers)
    assert r1.status_code == 200
    first = r1.json()

    # Change payload but reuse idempotency key — should return cached.
    payload2 = {**payload, "title": "Different Title"}
    r2 = await client.post("/api/v1/partners", json=payload2, headers=headers)
    assert r2.status_code == 200
    assert r2.json() == first


# ---------- contacts ----------

@pytest.mark.asyncio
async def test_contact_log_appears_in_history(client):
    _seed_firms(client.conn)
    headers = {"Authorization": "Bearer test-token"}
    await client.post(
        "/api/v1/partners",
        json={"firm_name": "Spencer Stuart", "name": "Sarah Whitfield"},
        headers=headers,
    )
    body = {
        "firm_name": "Spencer Stuart",
        "partner_name": "Sarah Whitfield",
        "contact_date": "2026-05-10",
        "channel": "email",
        "initiated_by": "me",
        "summary": "First outreach",
    }
    r = await client.post("/api/v1/contacts", json=body, headers=headers)
    assert r.status_code == 200
    partner_ulid = r.json()["partner_ulid"]

    history = await client.get(
        f"/api/v1/contacts?partner_ulid={partner_ulid}", headers=headers
    )
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["channel"] == "email"


# ---------- audit ----------

@pytest.mark.asyncio
async def test_audit_report_structure(client):
    _seed_firms(client.conn)
    headers = {"Authorization": "Bearer test-token"}
    r = await client.get("/api/v1/audit/report", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for key in (
        "generated_at",
        "primary_tier_coverage",
        "specialist_tier_coverage",
        "dormant_relationships",
        "open_follow_ups",
        "reciprocity_imbalances",
        "summary_actions",
    ):
        assert key in body


# ---------- search ----------

@pytest.mark.asyncio
async def test_search_finds_partner(client):
    _seed_firms(client.conn)
    headers = {"Authorization": "Bearer test-token"}
    await client.post(
        "/api/v1/partners",
        json={
            "firm_name": "TML Partners",
            "name": "Imogen Carr",
            "title": "Associate Partner",
            "practice": "Marketing leadership",
        },
        headers=headers,
    )
    r = await client.get("/api/v1/search?q=Imogen", headers=headers)
    assert r.status_code == 200
    hits = r.json()
    assert any(h["entity_type"] == "partner" for h in hits)


# ---------- export / import round-trip ----------

@pytest.mark.asyncio
async def test_export_import_round_trip(client):
    _seed_firms(client.conn)
    headers = {"Authorization": "Bearer test-token"}
    await client.post(
        "/api/v1/partners",
        json={"firm_name": "TML Partners", "name": "Imogen Carr", "title": "Associate Partner"},
        headers=headers,
    )
    await client.post(
        "/api/v1/contacts",
        json={
            "firm_name": "TML Partners",
            "partner_name": "Imogen Carr",
            "contact_date": "2026-05-02",
            "channel": "email",
            "initiated_by": "me",
            "summary": "Catch-up",
        },
        headers=headers,
    )

    exported = await client.get("/api/v1/export/markdown", headers=headers)
    assert exported.status_code == 200
    md = exported.text

    # Re-import into a separate fresh DB by swapping the override.
    other_conn = _fresh_conn()
    original = app.dependency_overrides[get_db]

    def _other_db():
        yield other_conn

    app.dependency_overrides[get_db] = _other_db
    try:
        r = await client.post(
            "/api/v1/import/markdown",
            json={"content": md, "overwrite_existing": False},
            headers=headers,
        )
        assert r.status_code == 200
        summary = r.json()
        assert summary["firms_created"] >= 1
        assert summary["partners_created"] >= 1
        assert summary["contacts_imported"] >= 1
    finally:
        app.dependency_overrides[get_db] = original
        other_conn.close()
