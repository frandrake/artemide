"""Board domain REST API — the six views, advisory advance, owner-only, no-bleed."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ARTEMIDE_API_TOKEN", "test-token")
os.environ["ARTEMIDE_N8N_TOKEN"] = "bot-token"
os.environ.setdefault("ARTEMIDE_COOKIE_SECRET", "test-cookie-secret")
os.environ.setdefault("ARTEMIDE_COOKIE_SECURE", "false")
os.environ.setdefault("ARTEMIDE_COOKIE_DOMAIN", "")

from src.app import app  # noqa: E402
from src.api.deps import get_db  # noqa: E402

OWNER = {"Authorization": "Bearer test-token"}
BOT = {"Authorization": "Bearer bot-token"}


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
async def test_six_views_and_flows(client):
    # Board-Search & Platform Log
    firm = (await client.post("/api/v1/board/firms", headers=OWNER, json={
        "name": "Nurole", "firm_type": "platform", "geography": ["UK"], "tier": 1,
        "status": "to_register"})).json()
    assert firm["geography"] == ["UK"]
    assert (await client.get("/api/v1/board/firms", headers=OWNER)).status_code == 200

    # Contact (R5 flag present in payload)
    contact = (await client.post("/api/v1/board/contacts", headers=OWNER, json={
        "name": "A Chair", "firm_ulid": firm["ulid"], "relationship": "warm"})).json()
    assert "verify_before_send" in contact

    # Board Opportunity Log
    opp = (await client.post("/api/v1/board/opportunities", headers=OWNER, json={
        "organisation": "Severn Trent plc", "board_type": "listed_ftse350", "role": "ned",
        "chair_contact_ulid": contact["ulid"]})).json()
    assert opp["chair_contact_ulid"] == contact["ulid"]
    ou = opp["ulid"]

    # Pipeline / advance — advisory R1 warning past conflict_screen
    await client.post(f"/api/v1/board/opportunities/{ou}/advance", headers=OWNER, json={"to_stage": "conflict_screen"})
    adv = (await client.post(f"/api/v1/board/opportunities/{ou}/advance", headers=OWNER,
                             json={"to_stage": "chair_meeting"})).json()
    assert adv["stage"] == "chair_meeting"
    assert len(adv["warnings"]) == 1

    # Conflict-screen queue + record
    pending = (await client.get("/api/v1/board/opportunities?conflict_cleared=pending", headers=OWNER)).json()
    assert any(o["ulid"] == ou for o in pending)
    screened = (await client.post(f"/api/v1/board/opportunities/{ou}/conflict-screen", headers=OWNER,
                                  json={"opportunity_ulid": ou, "is_sp_competitor": False, "result": "pass"})).json()
    assert screened["conflict_cleared"] == "yes"

    # Evaluation (built-in) + comparison
    detail = (await client.post(f"/api/v1/board/opportunities/{ou}/evaluate", headers=OWNER, json={
        "opportunity_ulid": ou,
        "score_chair_board_quality": 5, "score_mandate_contribution_fit": 5,
        "score_governance_health_risk": 4, "score_time_conflict_cost": 4,
        "score_brand_portfolio_value": 4, "score_terms": 5, "hard_disqualifiers": []})).json()
    assert detail["evaluation"]["verdict"] == "proceed"
    cmp = (await client.get(f"/api/v1/board/opportunities/evaluations/compare?ulid={ou}", headers=OWNER)).json()
    assert cmp["opportunities"][0]["weighted_total"] == detail["evaluation"]["weighted_total"]

    # Outreach due
    assert (await client.get("/api/v1/board/interactions/due", headers=OWNER)).status_code == 200
    assert (await client.get("/api/v1/board/tasks?status=open", headers=OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_board_is_owner_only_including_reads(client):
    # A bot token is rejected on every board surface, reads included.
    for path in ("/api/v1/board/firms", "/api/v1/board/contacts",
                 "/api/v1/board/opportunities", "/api/v1/board/competitors",
                 "/api/v1/board/tasks", "/api/v1/board/interactions/due",
                 "/api/v1/board/export/markdown"):
        r = await client.get(path, headers=BOT)
        assert r.status_code == 403, f"GET {path} → {r.status_code}"
        assert r.json()["error"] == "forbidden_role"
    r = await client.post("/api/v1/board/firms", headers=BOT, json={"name": "X"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_no_bleed_into_exec_search_and_firms(client):
    await client.post("/api/v1/board/firms", headers=OWNER, json={"name": "ZZZ Board Partners", "tier": 1})
    # exec global search must not surface the board firm
    res = (await client.get("/api/v1/search?q=ZZZ", headers=OWNER)).json()
    blob = str(res)
    assert "ZZZ Board Partners" not in blob
    # exec firm directory is untouched
    exec_firms = (await client.get("/api/v1/firms", headers=OWNER)).json()
    assert exec_firms == [] or all("ZZZ" not in (f.get("name") or "") for f in exec_firms)


@pytest.mark.asyncio
async def test_import_is_idempotent(client):
    ledger = (
        "# Artemide Board Ledger\n\n"
        "## Tier: 1\n\n"
        "### Firm: Spencer Stuart Board\n"
        "  - **Type:** big_five_board_practice\n"
        "  - **Geography:** UK, Europe\n"
        "  - **Status:** to_approach\n\n"
        "#### Contact: Jan Hall\n"
        "  - **Practice:** board\n"
        "  - **Relationship:** warm\n"
        "  - **Last-contact:** 2026-05-01\n\n"
    )
    r1 = (await client.post("/api/v1/board/import/markdown", headers=OWNER, json={"body": ledger})).json()
    assert r1["firms_created"] == 1 and r1["contacts_created"] == 1
    r2 = (await client.post("/api/v1/board/import/markdown", headers=OWNER, json={"body": ledger})).json()
    # Re-import creates nothing new (idempotent); it updates in place.
    assert r2["firms_created"] == 0 and r2["contacts_created"] == 0
    firms = (await client.get("/api/v1/board/firms", headers=OWNER)).json()
    assert len([f for f in firms if f["name"] == "Spencer Stuart Board"]) == 1
