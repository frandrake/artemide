"""/api/v1/comp-scenarios — REST round-trip + owner-only enforcement (reads too)."""
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
from src.repository import comp_scenarios as comp_repo  # noqa: E402

OWNER = {"Authorization": "Bearer test-token"}
BOT = {"Authorization": "Bearer bot-token"}

BASE = "/api/v1/comp-scenarios"


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


def _seed_baseline(conn) -> str:
    s = comp_repo.insert_scenario(
        conn, name="Current — S&P Global", status="current", is_baseline=True,
        base_gbp=200_000, cash_bonus_gbp=40_000,
    )
    return s.ulid


@pytest.mark.asyncio
async def test_crud_roundtrip(client):
    baseline_ulid = _seed_baseline(client.conn)

    # create
    r = await client.post(BASE, json={"name": "Offer A", "base_gbp": 250000}, headers=OWNER)
    assert r.status_code == 200
    created = r.json()
    assert created["status"] == "offer"
    assert created["totals"]["total_gbp"] == 250000
    assert "id" not in created and "engagement_id" not in created

    # list — baseline first
    r = await client.get(BASE, headers=OWNER)
    names = [s["name"] for s in r.json()]
    assert names == ["Current — S&P Global", "Offer A"]

    # get one
    r = await client.get(f"{BASE}/{created['ulid']}", headers=OWNER)
    assert r.status_code == 200 and r.json()["name"] == "Offer A"

    # patch — and explicit null clears
    r = await client.patch(
        f"{BASE}/{created['ulid']}",
        json={"cash_bonus_gbp": 30000, "base_gbp": None},
        headers=OWNER,
    )
    assert r.status_code == 200
    patched = r.json()
    assert patched["cash_bonus_gbp"] == 30000 and patched["base_gbp"] is None

    # compare
    r = await client.get(f"{BASE}/compare", headers=OWNER)
    assert r.status_code == 200
    body = r.json()
    assert body["baseline"]["ulid"] == baseline_ulid
    assert body["scenarios"][0]["deltas"]["cash_bonus_gbp"]["delta_gbp"] == -10000

    # compare with explicit scenario_ulid list (repeated param)
    r = await client.get(
        f"{BASE}/compare",
        params=[("scenario_ulid", created["ulid"])],
        headers=OWNER,
    )
    assert r.status_code == 200 and len(r.json()["scenarios"]) == 1

    # set baseline
    r = await client.post(f"{BASE}/{created['ulid']}/baseline", headers=OWNER)
    assert r.status_code == 200 and r.json()["is_baseline"] is True

    # delete the demoted ex-baseline, then restore it
    r = await client.delete(f"{BASE}/{baseline_ulid}", headers=OWNER)
    assert r.status_code == 204
    r = await client.get(BASE, headers=OWNER)
    assert [s["ulid"] for s in r.json()] == [created["ulid"]]
    r = await client.post(f"{BASE}/{baseline_ulid}/restore", headers=OWNER)
    assert r.status_code == 200 and r.json()["deleted_at"] is None


@pytest.mark.asyncio
async def test_delete_baseline_rejected(client):
    baseline_ulid = _seed_baseline(client.conn)
    r = await client.delete(f"{BASE}/{baseline_ulid}", headers=OWNER)
    assert r.status_code == 400  # ServiceValidationError → 400


@pytest.mark.asyncio
async def test_post_idempotency_replay(client):
    headers = {**OWNER, "Idempotency-Key": "comp-key-1"}
    r1 = await client.post(BASE, json={"name": "Offer A"}, headers=headers)
    r2 = await client.post(BASE, json={"name": "Offer A"}, headers=headers)
    assert r1.json() == r2.json()
    r = await client.get(BASE, headers=OWNER)
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_unknown_ulid_404(client):
    r = await client.get(f"{BASE}/01AAAAAAAAAAAAAAAAAAAAAAAA", headers=OWNER)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_compare_without_baseline_404(client):
    r = await client.get(f"{BASE}/compare", headers=OWNER)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_bot_forbidden_on_every_endpoint(client):
    """Comp scenarios deviate from other resources: even GETs are owner-only."""
    ulid = _seed_baseline(client.conn)
    attempts = [
        ("GET", BASE, None),
        ("POST", BASE, {"name": "X"}),
        ("GET", f"{BASE}/compare", None),
        ("GET", f"{BASE}/{ulid}", None),
        ("PATCH", f"{BASE}/{ulid}", {"base_gbp": 1}),
        ("POST", f"{BASE}/{ulid}/baseline", None),
        ("DELETE", f"{BASE}/{ulid}", None),
        ("POST", f"{BASE}/{ulid}/restore", None),
    ]
    for method, path, body in attempts:
        r = await client.request(method, path, json=body, headers=BOT)
        assert r.status_code == 403, f"{method} {path} returned {r.status_code}"
