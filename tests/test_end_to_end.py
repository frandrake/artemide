"""Cross-layer flows: seed → REST/MCP → audit."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("ARTEMIDE_API_TOKEN", "test-token")
os.environ.setdefault("ARTEMIDE_COOKIE_SECRET", "test-cookie-secret")
os.environ.setdefault("ARTEMIDE_COOKIE_SECURE", "false")
os.environ.setdefault("ARTEMIDE_COOKIE_DOMAIN", "")

from fastapi.testclient import TestClient  # noqa: E402

from scripts.seed_firms import seed_firms, seed_quarter_topics  # noqa: E402
from src.api.deps import get_db  # noqa: E402
from src.app import app  # noqa: E402
from src.mcp.tools.list_due_touches import list_due_touches  # noqa: E402
from src.mcp.tools.log_contact import log_contact  # noqa: E402
from src.mcp.tools.upsert_partner import upsert_partner  # noqa: E402
from src.models import (  # noqa: E402
    ContactChannel, FirmTier, GetPartnerStateInput, InitiatedBy,
    ListDueTouchesInput, LogContactInput, PlanQuarterInput, UpsertPartnerInput,
)
from src.mcp.tools.plan_quarter import plan_quarter  # noqa: E402
from src.repository import firms as firms_repo  # noqa: E402
from src.repository import partners as partners_repo  # noqa: E402
from src.services import ServiceContext  # noqa: E402
from src.services.audit_service import AuditService  # noqa: E402
from src.services.partners_service import PartnersService  # noqa: E402


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    db_file = tmp_path / "artemide.db"
    monkeypatch.setenv("ARTEMIDE_DB_PATH", str(db_file))
    # Use the production migration runner so schema_migrations is
    # populated correctly; subsequent init_db() calls then no-op.
    from src.db import init_db
    init_db(str(db_file))

    conn = sqlite3.connect(str(db_file), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ctx = ServiceContext(conn=conn, actor="FF", transport="system")
    seed_firms(ctx)
    seed_quarter_topics(ctx)
    yield conn
    conn.close()


def _override_db(conn: sqlite3.Connection):
    def _gen():
        yield conn
    return _gen


def test_seed_inserts_all_eleven_firms_and_four_quarters(seeded_db):
    firms = firms_repo.list_firms(seeded_db)
    assert len(firms) == 11
    by_tier = {f.tier.value for f in firms}
    assert by_tier == {"primary", "specialist"}  # NED not seeded
    tml = next(f for f in firms if f.name == "TML Partners")
    assert tml.relationship_state.value == "warm"

    audit_rows = seeded_db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE entity_type='firm' AND action='create'"
    ).fetchone()[0]
    assert audit_rows == 11

    quarters = seeded_db.execute("SELECT COUNT(*) FROM value_calendar").fetchone()[0]
    assert quarters == 4


def test_rest_log_contact_writes_audit_and_appears_in_listing(seeded_db):
    app.dependency_overrides[get_db] = _override_db(seeded_db)
    try:
        with TestClient(app) as c:
            h = {"Authorization": "Bearer test-token"}
            up = c.post(
                "/api/v1/partners",
                json={"firm_name": "Spencer Stuart", "name": "Sarah Whitfield", "title": "Partner"},
                headers=h,
            )
            assert up.status_code == 200, up.text
            partner_ulid = up.json()["ulid"]

            r = c.post(
                "/api/v1/contacts",
                json={
                    "firm_name": "Spencer Stuart",
                    "partner_name": "Sarah Whitfield",
                    "contact_date": "2026-05-12",
                    "channel": "email",
                    "initiated_by": "me",
                    "summary": "Cold outreach via WEF",
                    "value_given": "WEF brief",
                    "advance_state": True,
                },
                headers=h,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["partner_ulid"] == partner_ulid
            assert body["state_advanced"] is True

            listed = c.get(
                f"/api/v1/contacts?partner_ulid={partner_ulid}", headers=h,
            ).json()
            assert len(listed) == 1
            assert listed[0]["channel"] == "email"

            audit = c.get("/api/v1/audit/log?action=log_contact", headers=h).json()
            assert any(a["entity_id"] == listed[0]["ulid"] for a in audit)
    finally:
        app.dependency_overrides.clear()


def test_mcp_log_contact_produces_same_state_changes(seeded_db, monkeypatch):
    # MCP tools open their own connections via env-driven DB path; the
    # seeded_db fixture already monkeypatched ARTEMIDE_DB_PATH for us.
    ctx = ServiceContext(conn=seeded_db, actor="FF", transport="cli")
    partner = PartnersService.upsert(ctx, "Egon Zehnder", "Elena Brescia", title="Partner")

    out = log_contact(LogContactInput(
        partner_ulid=partner.ulid,
        contact_date=date(2026, 5, 15),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="MCP-initiated outreach",
        value_given="Strategic briefing",
    ))
    assert out["ok"] is True
    refreshed = partners_repo.get_partner_by_ulid(seeded_db, partner.ulid)
    assert refreshed is not None
    assert refreshed.last_contact_date == date(2026, 5, 15)
    assert refreshed.relationship_state.value == "warming"

    audit_via_mcp = seeded_db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE transport='mcp'"
    ).fetchone()[0]
    assert audit_via_mcp >= 1


def test_audit_report_flags_uncontacted_primary_firms(seeded_db):
    ctx = ServiceContext(conn=seeded_db, actor="FF", transport="cli")
    report = AuditService.generate_report(ctx)
    primary_flagged = [c for c in report.primary_tier_coverage if c.flagged]
    # All 5 primary firms have no partners after a fresh seed.
    assert len(primary_flagged) == 5
    assert any("no contactable partner" in (c.note or "") for c in primary_flagged)
    assert "Close 5 primary-tier coverage gaps" in report.summary_actions[0]


def test_plan_quarter_assigns_unique_weeks_across_primary(seeded_db):
    ctx = ServiceContext(conn=seeded_db, actor="FF", transport="cli")
    for firm_name in (
        "Spencer Stuart", "Heidrick & Struggles", "Russell Reynolds",
        "Egon Zehnder", "Korn Ferry",
    ):
        PartnersService.upsert(ctx, firm_name, f"Test {firm_name}", title="Partner")

    out = plan_quarter(PlanQuarterInput(year=2026, quarter=2))
    assert out["ok"] is True
    slots = out["slots"]
    assert len(slots) == 5
    weeks = [s["week_starting"] for s in slots]
    assert len(set(weeks)) == 5  # spacing rule respected
    assert out["topic"] is not None  # Q2 seed populated the topic
