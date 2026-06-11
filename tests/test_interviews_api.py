"""REST surface for interviews + transcripts (owner token)."""
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


async def _seed_engagement(client) -> str:
    await client.post("/api/v1/orgs", json={"name": "Acme Global"}, headers=AUTH)
    org_ulid = (await client.get("/api/v1/orgs", headers=AUTH)).json()[0]["ulid"]
    r = await client.post("/api/v1/engagements", json={"org_ulid": org_ulid, "role_title": "CMO"}, headers=AUTH)
    return r.json()["ulid"]


@pytest.mark.asyncio
async def test_interview_lifecycle(client):
    eng = await _seed_engagement(client)

    r = await client.post(
        f"/api/v1/engagements/{eng}/interviews",
        json={"interview_date": "2026-06-01", "round": 1, "format": "video",
              "summary": "strong", "transcript": "discussed quantum widgets"},
        headers=AUTH,
    )
    assert r.status_code == 200
    iv = r.json()
    ulid = iv["ulid"]
    assert iv["engagement_ulid"] == eng
    assert "engagement_id" not in iv and "engagement_log_id" not in iv

    # list = metadata, no transcript
    lst = (await client.get(f"/api/v1/engagements/{eng}/interviews", headers=AUTH)).json()
    assert len(lst) == 1
    assert "transcript" not in lst[0]

    # get without transcript
    g = (await client.get(f"/api/v1/interviews/{ulid}", headers=AUTH)).json()
    assert "transcript" not in g
    # get with transcript
    gt = (await client.get(f"/api/v1/interviews/{ulid}?include_transcript=true", headers=AUTH)).json()
    assert "quantum" in gt["transcript"]

    # patch fields
    p = await client.patch(f"/api/v1/interviews/{ulid}", json={"round": 2, "panel": "CEO"}, headers=AUTH)
    assert p.json()["round"] == 2

    # replace transcript
    pt = await client.put(f"/api/v1/interviews/{ulid}/transcript",
                          json={"transcript": "new verbatim body"}, headers=AUTH)
    assert pt.json()["transcript"] == "new verbatim body"

    # delete + restore
    assert (await client.delete(f"/api/v1/interviews/{ulid}", headers=AUTH)).status_code == 204
    assert (await client.post(f"/api/v1/interviews/{ulid}/restore", headers=AUTH)).status_code == 200
