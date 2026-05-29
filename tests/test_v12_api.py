"""Happy-path integration tests for the v1.2 REST surface (owner token)."""
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

    def _override_get_db():
        yield conn

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.conn = conn  # type: ignore[attr-defined]
        yield ac
    app.dependency_overrides.clear()
    conn.close()


@pytest.mark.asyncio
async def test_org_lifecycle_and_detail(client):
    r = await client.post("/api/v1/orgs", json={"name": "Acme Global", "scale_band": "fortune_500",
                                                 "pertinence_note": "coherent", "external_refs": {"website": "acme.com"}}, headers=AUTH)
    assert r.status_code == 200
    ulid = r.json()["ulid"]
    # idempotent upsert by name updates
    r2 = await client.post("/api/v1/orgs", json={"name": "Acme Global", "watch_state": "target"}, headers=AUTH)
    assert r2.json()["watch_state"] == "target"
    detail = (await client.get(f"/api/v1/orgs/{ulid}", headers=AUTH)).json()
    assert detail["name"] == "Acme Global"
    assert "engagements" in detail and "notes" in detail
    # soft delete + restore (owner)
    assert (await client.delete(f"/api/v1/orgs/{ulid}", headers=AUTH)).status_code == 204
    assert (await client.post(f"/api/v1/orgs/{ulid}/restore", headers=AUTH)).status_code == 200


@pytest.mark.asyncio
async def test_fit_profile_then_engagement_scores(client):
    # set an active profile (owner)
    body = {"comp_base_floor_gbp": 250000, "comp_total_target_gbp": 500000,
            "accepted_role_types": ["cmo"], "accepted_scale_bands": ["fortune_500"],
            "hard_exclusions": [], "weights": {"role_type": 50, "comp": 50}}
    assert (await client.put("/api/v1/fit/profile", json=body, headers=AUTH)).status_code == 200
    assert (await client.get("/api/v1/fit/profile", headers=AUTH)).status_code == 200
    org = (await client.post("/api/v1/orgs", json={"name": "Acme", "scale_band": "fortune_500"}, headers=AUTH)).json()
    eng = (await client.post("/api/v1/engagements", json={
        "org_ulid": org["ulid"], "role_title": "Group CMO", "role_type": "cmo",
        "comp_base_gbp": 300000, "comp_total_gbp": 500000}, headers=AUTH)).json()
    assert eng["fit_score"] == 100
    assert eng["org_ulid"] == org["ulid"]
    # advance + detail
    adv = (await client.post(f"/api/v1/engagements/{eng['ulid']}/advance",
                             json={"to_stage": "exploratory", "summary": "intro"}, headers=AUTH)).json()
    assert adv["stage"] == "exploratory"
    detail = (await client.get(f"/api/v1/engagements/{eng['ulid']}", headers=AUTH)).json()
    assert detail["log"] and detail["log"][0]["to_stage"] == "exploratory"
    assert "fit_breakdown" in detail and isinstance(detail["fit_breakdown"], dict)
    assert (await client.post("/api/v1/fit/rescore-all", headers=AUTH)).json()["rescored"] == 1


@pytest.mark.asyncio
async def test_message_approval_flow(client):
    m = (await client.post("/api/v1/messages", json={"body": "Hello", "kind": "cadence_touch"}, headers=AUTH)).json()
    assert m["status"] == "proposed"
    listed = (await client.get("/api/v1/messages?status=proposed", headers=AUTH)).json()
    assert len(listed) == 1
    approved = (await client.post(f"/api/v1/messages/{m['ulid']}/approve", headers=AUTH)).json()
    assert approved["status"] == "approved"
    sent = (await client.post(f"/api/v1/messages/{m['ulid']}/sent", headers=AUTH)).json()
    assert sent["status"] == "sent"


@pytest.mark.asyncio
async def test_programme_status_and_milestones(client):
    await client.post("/api/v1/programme/milestones",
                      json={"phase": "close", "label": "Offer", "target_date": "2027-03-24",
                            "metric_note": "≥1 at offer"}, headers=AUTH)
    ms = (await client.get("/api/v1/programme/milestones", headers=AUTH)).json()
    assert len(ms) == 1
    status = (await client.get("/api/v1/programme/status", headers=AUTH)).json()
    assert "overall_rag" in status and "days_to_target" in status
    assert any(p["phase"] == "close" for p in status["phases"])
