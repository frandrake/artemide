"""REST surface for attachments — multipart upload + binary download."""
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
PDF = b"%PDF-1.4 small body here"


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


async def _seed_org(client) -> str:
    await client.post("/api/v1/orgs", json={"name": "Acme Global"}, headers=AUTH)
    return (await client.get("/api/v1/orgs", headers=AUTH)).json()[0]["ulid"]


@pytest.mark.asyncio
async def test_upload_download_delete(client):
    org = await _seed_org(client)

    r = await client.post(
        "/api/v1/attachments",
        files={"file": ("spec.pdf", PDF, "application/pdf")},
        data={"entity_type": "org", "entity_ulid": org, "kind": "job_spec"},
        headers=AUTH,
    )
    assert r.status_code == 200
    meta = r.json()
    ulid = meta["ulid"]
    assert meta["byte_size"] == len(PDF)
    assert "content" not in meta  # bytes never serialised

    # list
    lst = (await client.get(f"/api/v1/attachments?entity_type=org&entity_ulid={org}", headers=AUTH)).json()
    assert len(lst) == 1

    # download returns exact bytes + Content-Disposition
    dl = await client.get(f"/api/v1/attachments/{ulid}/content", headers=AUTH)
    assert dl.status_code == 200
    assert dl.content == PDF
    assert "spec.pdf" in dl.headers["content-disposition"]

    # bad mime → 400
    bad = await client.post(
        "/api/v1/attachments",
        files={"file": ("x.exe", b"MZ", "application/x-msdownload")},
        data={"entity_type": "org", "entity_ulid": org, "kind": "other"},
        headers=AUTH,
    )
    assert bad.status_code == 400

    # delete + restore
    assert (await client.delete(f"/api/v1/attachments/{ulid}", headers=AUTH)).status_code == 204
    assert (await client.post(f"/api/v1/attachments/{ulid}/restore", headers=AUTH)).status_code == 200
