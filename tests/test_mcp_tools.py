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


# ---------- v1.3: interviews + attachments tools ----------

def _seed_engagement(path: str) -> str:
    from src.repository import engagements as engagements_repo
    from src.repository import orgs as orgs_repo

    conn, _ = _ctx(path)
    try:
        org = orgs_repo.insert_org(conn, name="Acme Global")
        eng = engagements_repo.insert_engagement(conn, org_id=org.id, role_title="CMO")
        return eng.ulid
    finally:
        conn.close()


def test_interview_tools_omit_transcript_until_requested(db_path):
    import base64

    from src.models import (
        AttachFileInput,
        AttachmentEntityType,
        AttachmentKind,
        GetInterviewInput,
        InterviewFormat,
        ListInterviewsInput,
        LogInterviewInput,
    )
    from src.mcp.tools.attach_file import attach_file
    from src.mcp.tools.get_interview import get_interview
    from src.mcp.tools.list_interviews import list_interviews
    from src.mcp.tools.log_interview import log_interview

    eng = _seed_engagement(db_path)

    logged = log_interview(LogInterviewInput(
        engagement_ulid=eng, interview_date=date(2026, 6, 1), round="first",
        format=InterviewFormat.video, summary="strong",
        transcript="discussed quantum widgets",
    ))
    assert logged["ok"] is True
    assert "transcript" not in logged["interview"]
    ulid = logged["interview"]["ulid"]

    listed = list_interviews(ListInterviewsInput(engagement_ulid=eng))
    assert listed["ok"] is True
    assert "transcript" not in listed["interviews"][0]

    got = get_interview(GetInterviewInput(interview_ulid=ulid, include_transcript=True))
    assert "quantum" in got["interview"]["transcript"]

    # attach_file happy path + > 4 MB rejection
    ok = attach_file(AttachFileInput(
        entity_type=AttachmentEntityType.engagement, entity_ulid=eng,
        kind=AttachmentKind.job_spec, filename="spec.pdf", content_type="application/pdf",
        content_base64=base64.b64encode(b"%PDF-1.4 body").decode("ascii"),
    ))
    assert ok["ok"] is True

    too_big = attach_file(AttachFileInput(
        entity_type=AttachmentEntityType.engagement, entity_ulid=eng,
        kind=AttachmentKind.other, filename="big.pdf", content_type="application/pdf",
        content_base64=base64.b64encode(b"x" * (5 * 1024 * 1024)).decode("ascii"),
    ))
    assert too_big["ok"] is False
    assert too_big["error"] == "validation_error"


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


# ---------- comp comparison tools ----------

def _seed_comp(path: str) -> tuple[str, str]:
    """Return (baseline_ulid, offer_ulid)."""
    from src.repository import comp_scenarios as comp_repo

    conn, _ = _ctx(path)
    try:
        baseline = comp_repo.insert_scenario(
            conn, name="Current — S&P Global", status="current", is_baseline=True,
            base_gbp=200_000, cash_bonus_gbp=40_000,
        )
        offer = comp_repo.insert_scenario(conn, name="Offer A", base_gbp=250_000)
        return baseline.ulid, offer.ulid
    finally:
        conn.close()


def test_upsert_comp_scenario_happy_path(db_path):
    from src.mcp.tools.upsert_comp_scenario import upsert_comp_scenario
    from src.models import UpsertCompScenarioInput

    out = upsert_comp_scenario(UpsertCompScenarioInput(
        name="Offer B", base_gbp=260_000, pension_pct=10.0,
    ))
    assert out["ok"] is True
    assert out["scenario"]["name"] == "Offer B"
    assert out["scenario"]["status"] == "offer"
    assert out["scenario"]["engagement_ulid"] is None
    assert out["scenario"]["totals"]["total_gbp"] == 260_000 + 26_000


def test_upsert_comp_scenario_engagement_mapping(db_path):
    from src.mcp.tools.upsert_comp_scenario import upsert_comp_scenario
    from src.models import UpsertCompScenarioInput
    from src.repository import engagements as engagements_repo
    from src.repository import orgs as orgs_repo

    conn, _ = _ctx(db_path)
    try:
        org = orgs_repo.insert_org(conn, name="Acme")
        eng = engagements_repo.insert_engagement(conn, org_id=org.id, role_title="CMO")
    finally:
        conn.close()
    out = upsert_comp_scenario(UpsertCompScenarioInput(name="Offer B", engagement_ulid=eng.ulid))
    assert out["ok"] is True
    assert out["scenario"]["engagement_ulid"] == eng.ulid
    assert out["scenario"]["engagement_org_name"] == "Acme"


def test_list_comp_scenarios_returns_baseline_first(db_path):
    from src.mcp.tools.list_comp_scenarios import list_comp_scenarios
    from src.models import ListCompScenariosInput

    baseline_ulid, offer_ulid = _seed_comp(db_path)
    out = list_comp_scenarios(ListCompScenariosInput())
    assert out["ok"] is True
    assert out["baseline_ulid"] == baseline_ulid
    assert [s["ulid"] for s in out["scenarios"]] == [baseline_ulid, offer_ulid]


def test_compare_comp_deltas(db_path):
    from src.mcp.tools.compare_comp import compare_comp
    from src.models import CompareCompInput

    baseline_ulid, offer_ulid = _seed_comp(db_path)
    out = compare_comp(CompareCompInput())
    assert out["ok"] is True
    assert out["baseline"]["ulid"] == baseline_ulid
    deltas = out["scenarios"][0]["deltas"]
    assert deltas["base_gbp"]["delta_gbp"] == 50_000
    assert deltas["total_gbp"]["delta_gbp"] == 250_000 - 240_000


def test_compare_comp_without_baseline_not_found(db_path):
    from src.mcp.tools.compare_comp import compare_comp
    from src.models import CompareCompInput

    out = compare_comp(CompareCompInput())
    assert out == {"ok": False, "error": "not_found", "message": "no baseline scenario set"}


def test_delete_comp_scenario(db_path):
    from src.mcp.tools.delete_comp_scenario import delete_comp_scenario
    from src.mcp.tools.list_comp_scenarios import list_comp_scenarios
    from src.models import DeleteCompScenarioInput, ListCompScenariosInput

    baseline_ulid, offer_ulid = _seed_comp(db_path)
    out = delete_comp_scenario(DeleteCompScenarioInput(ulid=offer_ulid))
    assert out == {"ok": True, "deleted": offer_ulid}
    listed = list_comp_scenarios(ListCompScenariosInput())
    assert [s["ulid"] for s in listed["scenarios"]] == [baseline_ulid]
    # the baseline refuses deletion
    refused = delete_comp_scenario(DeleteCompScenarioInput(ulid=baseline_ulid))
    assert refused["ok"] is False and refused["error"] == "validation_error"
