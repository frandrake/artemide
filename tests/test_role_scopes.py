"""Rule 18 — owner/bot scope enforcement on every restricted endpoint (REST)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Pin tokens before importing the app: owner + bot resolve via the env fallback.
os.environ.setdefault("ARTEMIDE_API_TOKEN", "test-token")
os.environ["ARTEMIDE_N8N_TOKEN"] = "bot-token"
os.environ.setdefault("ARTEMIDE_COOKIE_SECRET", "test-cookie-secret")
os.environ.setdefault("ARTEMIDE_COOKIE_SECURE", "false")
os.environ.setdefault("ARTEMIDE_COOKIE_DOMAIN", "")

from src.app import app  # noqa: E402
from src.api.deps import get_db  # noqa: E402

OWNER = {"Authorization": "Bearer test-token"}
BOT = {"Authorization": "Bearer bot-token"}

_PROFILE_BODY = {
    "comp_base_floor_gbp": 250000, "comp_total_target_gbp": 500000,
    "accepted_role_types": ["cmo"], "accepted_scale_bands": ["fortune_500"],
    "hard_exclusions": [], "weights": {"role_type": 100},
}


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


async def _seed(client) -> dict:
    org = (await client.post("/api/v1/orgs", json={"name": "Acme", "scale_band": "fortune_500"}, headers=BOT)).json()
    eng = (await client.post("/api/v1/engagements", json={"org_ulid": org["ulid"], "role_title": "CMO", "role_type": "cmo"}, headers=BOT)).json()
    msg = (await client.post("/api/v1/messages", json={"body": "hi"}, headers=BOT)).json()
    return {"org": org["ulid"], "eng": eng["ulid"], "msg": msg["ulid"]}


@pytest.mark.asyncio
async def test_bot_can_create_and_read(client):
    r = await client.post("/api/v1/orgs", json={"name": "Acme", "scale_band": "fortune_500"}, headers=BOT)
    assert r.status_code == 200
    assert (await client.get("/api/v1/orgs", headers=BOT)).status_code == 200
    assert (await client.get("/api/v1/programme/status", headers=BOT)).status_code == 200


@pytest.mark.asyncio
async def test_owner_only_endpoints_reject_bot(client):
    ids = await _seed(client)
    owner_only = [
        ("delete", f"/api/v1/orgs/{ids['org']}", None),
        ("post", f"/api/v1/orgs/{ids['org']}/restore", None),
        ("delete", f"/api/v1/engagements/{ids['eng']}", None),
        ("post", f"/api/v1/engagements/{ids['eng']}/restore", None),
        ("put", "/api/v1/fit/profile", _PROFILE_BODY),
        ("post", "/api/v1/fit/rescore-all", None),
        ("patch", f"/api/v1/messages/{ids['msg']}", {"body": "x"}),
        ("post", f"/api/v1/messages/{ids['msg']}/approve", None),
        ("post", f"/api/v1/messages/{ids['msg']}/discard", None),
        ("post", "/api/v1/programme/milestones", {"phase": "seed", "label": "x", "target_date": "2026-09-30"}),
    ]
    for method, path, body in owner_only:
        resp = await getattr(client, method)(path, json=body, headers=BOT) if body is not None \
            else await getattr(client, method)(path, headers=BOT)
        assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
        assert resp.json()["error"] == "forbidden_role", f"{method} {path}"


@pytest.mark.asyncio
async def test_owner_can_perform_owner_only(client):
    ids = await _seed(client)
    assert (await client.put("/api/v1/fit/profile", json=_PROFILE_BODY, headers=OWNER)).status_code == 200
    assert (await client.post(f"/api/v1/messages/{ids['msg']}/approve", headers=OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_blocked_attempts_are_audited(client):
    ids = await _seed(client)
    await client.post(f"/api/v1/messages/{ids['msg']}/approve", headers=BOT)
    denied = client.conn.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'denied'").fetchone()[0]
    assert denied >= 1


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client):
    assert (await client.get("/api/v1/orgs")).status_code == 401
