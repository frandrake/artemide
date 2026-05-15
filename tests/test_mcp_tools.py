"""MCP tool tests — both direct (calling the underlying functions) and
one HTTP-level integration test against the mounted /mcp endpoint."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

os.environ["ARTEMIDE_API_TOKEN"] = "test-token"
os.environ["ARTEMIDE_COOKIE_SECRET"] = "test-cookie-secret"
os.environ["ARTEMIDE_COOKIE_SECURE"] = "false"
os.environ["ARTEMIDE_COOKIE_DOMAIN"] = ""

from src.models import (  # noqa: E402
    ContactChannel,
    FirmTier,
    GetPartnerStateInput,
    ImportMarkdownInput,
    InitiatedBy,
    ListDueTouchesInput,
    LogContactInput,
    PlanQuarterInput,
    RelationshipState,
    SetQuarterTopicInput,
    UpsertPartnerInput,
    CalendarStatus,
)
from src.mcp.server import mcp  # noqa: E402
from src.mcp.tools.audit_ledger import audit_ledger  # noqa: E402
from src.mcp.tools.get_partner_state import get_partner_state  # noqa: E402
from src.mcp.tools.import_markdown import import_markdown  # noqa: E402
from src.mcp.tools.list_due_touches import list_due_touches  # noqa: E402
from src.mcp.tools.log_contact import log_contact  # noqa: E402
from src.mcp.tools.plan_quarter import plan_quarter  # noqa: E402
from src.mcp.tools.set_quarter_topic import set_quarter_topic  # noqa: E402
from src.mcp.tools.upsert_partner import upsert_partner  # noqa: E402
from src.repository import firms as firms_repo  # noqa: E402
from src.repository import partners as partners_repo  # noqa: E402
from src.services import ServiceContext  # noqa: E402
from src.services.contacts_service import ContactsService  # noqa: E402
from src.services.export_service import ExportService  # noqa: E402
from src.services.firms_service import FirmsService  # noqa: E402
from src.services.partners_service import PartnersService  # noqa: E402


# ---------- shared fixture: ephemeral DB file used by tools via env ----------

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "artemide.db"
    monkeypatch.setenv("ARTEMIDE_DB_PATH", str(p))
    # initialise schema
    conn = sqlite3.connect(str(p), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for m in sorted(Path("migrations").glob("*.sql")):
        conn.executescript(m.read_text())
    conn.close()
    return str(p)


def _ctx(path: str) -> tuple[sqlite3.Connection, ServiceContext]:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn, ServiceContext(conn=conn, actor="FF", transport="cli")


def _seed_basic(path: str) -> tuple[str, str]:
    """Return (firm_ulid, partner_ulid)."""
    conn, ctx = _ctx(path)
    try:
        firm = firms_repo.insert_firm(
            conn, name="TML Partners", tier=FirmTier.specialist, region="London"
        )
        partner = PartnersService.upsert(ctx, firm.name, "Imogen Carr", title="Partner")
        return firm.ulid, partner.ulid
    finally:
        conn.close()


# ---------- direct tool tests ----------

def test_log_contact_happy_path(db_path):
    _, partner_ulid = _seed_basic(db_path)
    out = log_contact(LogContactInput(
        partner_ulid=partner_ulid,
        contact_date=date(2026, 5, 10),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="Catch-up",
        value_given="Shared a report",
    ))
    assert out["ok"] is True
    assert out["partner_ulid"] == partner_ulid
    assert out["contact"]["channel"] == "email"


def test_log_contact_partner_not_found(db_path):
    out = log_contact(LogContactInput(
        partner_ulid="01AAAAAAAAAAAAAAAAAAAAAAAA",
        contact_date=date(2026, 5, 10),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
    ))
    assert out == {
        "ok": False, "error": "not_found",
        "message": "partner not found: 01AAAAAAAAAAAAAAAAAAAAAAAA",
    }


def test_upsert_partner_create_then_update(db_path):
    firm_ulid, _ = _seed_basic(db_path)
    first = upsert_partner(UpsertPartnerInput(
        firm_ulid=firm_ulid, name="Hugh Bairstow", title="Associate Partner",
    ))
    second = upsert_partner(UpsertPartnerInput(
        firm_ulid=firm_ulid, name="Hugh Bairstow", title="Partner",
    ))
    assert first["ok"] and second["ok"]
    assert first["partner"]["ulid"] == second["partner"]["ulid"]
    assert second["partner"]["title"] == "Partner"


def test_get_partner_state_returns_history(db_path):
    _, partner_ulid = _seed_basic(db_path)
    log_contact(LogContactInput(
        partner_ulid=partner_ulid,
        contact_date=date(2026, 5, 1),
        channel=ContactChannel.coffee,
        initiated_by=InitiatedBy.me,
        summary="Coffee chat",
    ))
    out = get_partner_state(GetPartnerStateInput(partner_ulid=partner_ulid))
    assert out["ok"] is True
    assert out["partner"]["ulid"] == partner_ulid
    assert len(out["contacts"]) == 1


def test_list_due_touches_classifies_partners(db_path):
    conn, ctx = _ctx(db_path)
    try:
        primary = firms_repo.insert_firm(conn, name="Primary Co", tier=FirmTier.primary)
        specialist = firms_repo.insert_firm(conn, name="Spec Co", tier=FirmTier.specialist)
        today = date.today()

        overdue = PartnersService.upsert(ctx, primary.name, "Overdue P")
        partners_repo.update_partner_fields(
            conn, overdue.id, {"last_contact_date": today - timedelta(days=125)},
        )

        soon = PartnersService.upsert(
            ctx, primary.name, "Due-Soon P",
            next_touch_date=today + timedelta(days=5),
        )

        none = PartnersService.upsert(ctx, specialist.name, "Unplanned S")
    finally:
        conn.close()

    out = list_due_touches(ListDueTouchesInput(window_days=14))
    assert out["ok"] is True
    statuses = {(d["partner_name"], d["status"]) for d in out["due_touches"]}
    assert ("Overdue P", "overdue") in statuses
    assert ("Due-Soon P", "due_soon") in statuses
    assert ("Unplanned S", "no_planned_touch") in statuses


def test_plan_quarter_with_topic(db_path):
    conn, ctx = _ctx(db_path)
    try:
        firm = firms_repo.insert_firm(conn, name="Plan Primary", tier=FirmTier.primary)
        PartnersService.upsert(ctx, firm.name, "Plan Partner")
    finally:
        conn.close()
    set_quarter_topic(SetQuarterTopicInput(
        year=2026, quarter=2, topic="Agentic CMO themes",
    ))
    out = plan_quarter(PlanQuarterInput(year=2026, quarter=2))
    assert out["ok"] is True
    assert out["topic"] == "Agentic CMO themes"
    assert len(out["slots"]) == 1


def test_set_quarter_topic_upsert(db_path):
    a = set_quarter_topic(SetQuarterTopicInput(year=2026, quarter=3, topic="Topic A"))
    b = set_quarter_topic(SetQuarterTopicInput(year=2026, quarter=3, topic="Topic B",
                                                  status=CalendarStatus.in_progress))
    assert a["quarter"]["ulid"] == b["quarter"]["ulid"]
    assert b["quarter"]["topic"] == "Topic B"
    assert b["quarter"]["status"] == "in_progress"


def test_audit_ledger_has_all_sections(db_path):
    _seed_basic(db_path)
    out = audit_ledger()
    assert out["ok"] is True
    report = out["report"]
    for key in (
        "generated_at",
        "primary_tier_coverage",
        "specialist_tier_coverage",
        "dormant_relationships",
        "open_follow_ups",
        "reciprocity_imbalances",
        "summary_actions",
    ):
        assert key in report


def test_import_markdown_idempotent(db_path):
    _, partner_ulid = _seed_basic(db_path)
    log_contact(LogContactInput(
        partner_ulid=partner_ulid,
        contact_date=date(2026, 5, 2),
        channel=ContactChannel.email,
        initiated_by=InitiatedBy.me,
        summary="First touch",
    ))

    conn, ctx = _ctx(db_path)
    try:
        md = ExportService.export_to_markdown(ctx)
    finally:
        conn.close()

    # Re-import into a fresh DB. We need to swap the env-driven DB path.
    fresh = Path(db_path).parent / "fresh.db"
    os.environ["ARTEMIDE_DB_PATH"] = str(fresh)
    conn = sqlite3.connect(str(fresh), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for m in sorted(Path("migrations").glob("*.sql")):
        conn.executescript(m.read_text())
    conn.close()

    first = import_markdown(ImportMarkdownInput(body=md))
    second = import_markdown(ImportMarkdownInput(body=md))
    assert first["ok"] and second["ok"]
    assert first["summary"]["contacts_imported"] == 1
    assert second["summary"]["contacts_imported"] == 0
    assert second["summary"]["contacts_skipped"] >= 1


# ---------- integration test via in-process FastMCP Client ----------

@pytest_asyncio.fixture
async def mcp_client():
    from fastmcp import Client
    async with Client(mcp) as c:
        yield c


@pytest.mark.asyncio
async def test_list_tools_registered(mcp_client):
    tools = await mcp_client.list_tools()
    names = set(t.name for t in tools)
    expected = {
        "audit_ledger",
        "create_draft",
        "create_template",
        "get_draft",
        "get_partner_state",
        "import_markdown",
        "list_drafts",
        "list_due_touches",
        "list_engagements",
        "list_templates",
        "log_contact",
        "mark_sent",
        "outreach_metrics",
        "pipeline_snapshot",
        "plan_quarter",
        "render_template",
        "set_outreach_stage",
        "set_quarter_topic",
        "update_draft",
        "update_engagement",
        "upsert_partner",
    }
    assert expected.issubset(names), f"missing tools: {expected - names}"


@pytest.mark.asyncio
async def test_call_tool_via_client(db_path, mcp_client):
    firm_ulid, _ = _seed_basic(db_path)
    result = await mcp_client.call_tool(
        "upsert_partner",
        {"payload": {"firm_ulid": firm_ulid, "name": "Hugh Bairstow", "title": "Partner"}},
    )
    payload = result.data if hasattr(result, "data") else result.structured_content
    assert payload["ok"] is True
    assert payload["partner"]["name"] == "Hugh Bairstow"


# ---------- HTTP-level test: /mcp auth gate ----------

def test_mcp_http_requires_auth():
    """TestClient drives the ASGI lifespan, so FastMCP's session manager
    initialises and the /mcp endpoint is reachable."""
    from fastapi.testclient import TestClient
    from src.app import app

    with TestClient(app) as c:
        r = c.post("/mcp/", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        assert r.status_code == 401

        r2 = c.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer test-token",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        )
        # Bearer middleware lets the request through; FastMCP handles
        # the protocol below. Anything other than 401 confirms the gate.
        assert r2.status_code != 401
