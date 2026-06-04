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
async def test_events_flow_and_ack(client):
    org = (await client.post("/api/v1/orgs", json={"name": "Acme", "scale_band": "fortune_500"}, headers=AUTH)).json()
    eng = (await client.post("/api/v1/engagements", json={"org_ulid": org["ulid"], "role_title": "CMO", "role_type": "cmo"}, headers=AUTH)).json()
    await client.post(f"/api/v1/engagements/{eng['ulid']}/advance", json={"to_stage": "exploratory"}, headers=AUTH)
    m = (await client.post("/api/v1/messages", json={"body": "hi"}, headers=AUTH)).json()
    await client.post(f"/api/v1/messages/{m['ulid']}/approve", headers=AUTH)

    events = (await client.get("/api/v1/events", headers=AUTH)).json()
    types = {e["event_type"] for e in events}
    assert {"engagement.surfaced", "engagement.stage_changed", "message.approved"} <= types

    first = events[0]["ulid"]
    ack = (await client.post(f"/api/v1/events/{first}/ack", headers=AUTH)).json()
    assert ack["delivered"] is True
    remaining = (await client.get("/api/v1/events", headers=AUTH)).json()
    assert first not in {e["ulid"] for e in remaining}

    health = (await client.get("/api/v1/events/health", headers=AUTH)).json()
    assert health["undelivered"] == len(remaining)


@pytest.mark.asyncio
async def test_reciprocity_suggestion_on_advance(client):
    # seed a firm + partner directly so the engagement can be partner-sourced
    from src.models import FirmTier
    from src.repository import firms as firms_repo, partners as partners_repo
    firm = firms_repo.insert_firm(client.conn, name="TML", tier=FirmTier.specialist, region="London")
    partner = partners_repo.insert_partner(client.conn, firm_id=firm.id, name="Jane")
    org = (await client.post("/api/v1/orgs", json={"name": "Acme", "scale_band": "fortune_500"}, headers=AUTH)).json()
    eng = (await client.post("/api/v1/engagements", json={
        "org_ulid": org["ulid"], "role_title": "CMO", "role_type": "cmo",
        "source_partner_ulid": partner.ulid}, headers=AUTH)).json()
    adv = (await client.post(f"/api/v1/engagements/{eng['ulid']}/advance", json={"to_stage": "exploratory"}, headers=AUTH)).json()
    assert adv["reciprocity_suggestion"] and "Jane" in adv["reciprocity_suggestion"]


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


@pytest.mark.asyncio
async def test_engagements_list_is_not_n_plus_1(client):
    """The list endpoint batch-loads orgs/partners — query count must not grow
    per row (regression guard for the N+1 that _engagement_response had)."""
    o1 = (await client.post("/api/v1/orgs", json={"name": "Org One", "scale_band": "fortune_500"}, headers=AUTH)).json()
    o2 = (await client.post("/api/v1/orgs", json={"name": "Org Two", "scale_band": "fortune_500"}, headers=AUTH)).json()
    for org, title in ((o1, "CMO A"), (o1, "CMO B"), (o2, "CMO C")):
        await client.post("/api/v1/engagements",
                          json={"org_ulid": org["ulid"], "role_title": title, "role_type": "cmo"},
                          headers=AUTH)

    sql_log: list[str] = []
    client.conn.set_trace_callback(sql_log.append)
    try:
        r = await client.get("/api/v1/engagements", headers=AUTH)
    finally:
        client.conn.set_trace_callback(None)

    assert r.status_code == 200 and len(r.json()) == 3
    # one batched org lookup regardless of row count (was one-per-row before)
    assert sum(1 for s in sql_log if "FROM organisations" in s) <= 1, sql_log
    assert sum(1 for s in sql_log if "FROM partners" in s) <= 1, sql_log
    # the enriched fields are still correct
    names = {e["org_name"] for e in r.json()}
    assert names == {"Org One", "Org Two"}
    assert all(e["org_scale_band"] == "fortune_500" for e in r.json())


@pytest.mark.asyncio
async def test_draft_list_exposes_partner_ulid(client):
    """The drafts list injects partner_ulid (id is stripped) so the global
    Drafts page can open the editor for the right partner."""
    from src.models import FirmTier
    from src.repository import firms as firms_repo
    from src.repository import outreach as outreach_repo
    from src.repository import partners as partners_repo

    firm = firms_repo.insert_firm(client.conn, name="TML", tier=FirmTier.specialist)
    partner = partners_repo.insert_partner(client.conn, firm_id=firm.id, name="Imogen Carr")
    outreach_repo.insert_draft(client.conn, partner_id=partner.id, channel="email", body="hi")

    rows = (await client.get("/api/v1/outreach/drafts", headers=AUTH)).json()
    assert len(rows) == 1
    assert rows[0]["partner_ulid"] == partner.ulid
    assert "partner_id" not in rows[0]  # internal pk stays stripped
