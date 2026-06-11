"""CompService — scenario CRUD, totals, comparison, baseline rules, owner gate."""
from __future__ import annotations

import pytest

from src.models import (
    CompScenarioStatus,
    CompScenarioUpdateInput,
    UpsertCompScenarioInput,
)
from src.repository import comp_scenarios as comp_repo
from src.repository import orgs as orgs_repo
from src.repository import engagements as engagements_repo
from src.services import ServiceContext
from src.services.comp_service import CompService, _totals
from src.services.exceptions import (
    ConflictError,
    ForbiddenRoleError,
    NotFoundError,
    ValidationError,
)

BASELINE_NAME = "Current — S&P Global"


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="cli")


@pytest.fixture
def bot_ctx(db):
    return ServiceContext(conn=db, actor="n8n", transport="rest", role="bot")


def _seed_baseline(db, **comp):
    return comp_repo.insert_scenario(
        db, name=BASELINE_NAME, status="current", is_baseline=True, **comp
    )


def _seed_engagement(db):
    org = orgs_repo.insert_org(db, name="Acme")
    return engagements_repo.insert_engagement(db, org_id=org.id, role_title="CMO")


def _audit_rows(db, action=None):
    sql = "SELECT * FROM audit_log WHERE entity_type = 'comp_scenario'"
    params = []
    if action:
        sql += " AND action = ?"
        params.append(action)
    return db.execute(sql, params).fetchall()


# ---------- totals ----------

def test_totals_all_none_are_zero(db, ctx):
    s = comp_repo.insert_scenario(db, name="Empty")
    assert _totals(s) == {"pension_value_gbp": 0, "total_cash_gbp": 0, "total_gbp": 0}


def test_totals_math_and_pension_rounding(db):
    s = comp_repo.insert_scenario(
        db, name="Full", base_gbp=250_000, cash_bonus_gbp=75_000, equity_gbp=100_000,
        pension_pct=10.5, healthcare_gbp=2_000, car_allowance_gbp=6_000, other_gbp=1_000,
    )
    t = _totals(s)
    assert t["pension_value_gbp"] == 26_250  # 250000 * 10.5%
    assert t["total_cash_gbp"] == 325_000
    assert t["total_gbp"] == 325_000 + 100_000 + 26_250 + 2_000 + 6_000 + 1_000


# ---------- upsert ----------

def test_upsert_creates_with_defaults(db, ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=300_000))
    assert s.status == CompScenarioStatus.offer
    assert s.is_baseline is False
    assert s.base_gbp == 300_000
    assert len(_audit_rows(db, "create")) == 1


def test_upsert_matches_by_name_and_updates(db, ctx):
    first = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=300_000))
    second = CompService.upsert(
        ctx, UpsertCompScenarioInput(name="Offer A", cash_bonus_gbp=50_000)
    )
    assert second.ulid == first.ulid
    assert second.base_gbp == 300_000  # untouched (exclude_none)
    assert second.cash_bonus_gbp == 50_000
    assert len(_audit_rows(db, "update")) == 1


def test_upsert_matches_by_ulid(db, ctx):
    first = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    renamed = CompService.upsert(
        ctx, UpsertCompScenarioInput(ulid=first.ulid, name="Offer A v2")
    )
    assert renamed.ulid == first.ulid
    assert renamed.name == "Offer A v2"


def test_upsert_resolves_engagement_ulid(db, ctx):
    e = _seed_engagement(db)
    s = CompService.upsert(
        ctx, UpsertCompScenarioInput(name="Offer A", engagement_ulid=e.ulid)
    )
    assert s.engagement_id == e.id
    payload = CompService.to_payload(ctx, s)
    assert payload["engagement_ulid"] == e.ulid
    assert payload["engagement_role_title"] == "CMO"
    assert payload["engagement_org_name"] == "Acme"
    assert "engagement_id" not in payload


def test_upsert_dangling_engagement_raises(db, ctx):
    with pytest.raises(NotFoundError):
        CompService.upsert(
            ctx,
            UpsertCompScenarioInput(
                name="Offer A", engagement_ulid="01AAAAAAAAAAAAAAAAAAAAAAAA"
            ),
        )


# ---------- update_fields ----------

def test_update_fields_can_null_a_field(db, ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=300_000))
    updated = CompService.update_fields(
        ctx, s.ulid, CompScenarioUpdateInput(base_gbp=None)
    )
    assert updated.base_gbp is None


def test_update_fields_empty_payload_rejected(db, ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    with pytest.raises(ValidationError):
        CompService.update_fields(ctx, s.ulid, CompScenarioUpdateInput())


def test_update_fields_clears_engagement_link(db, ctx):
    e = _seed_engagement(db)
    s = CompService.upsert(
        ctx, UpsertCompScenarioInput(name="Offer A", engagement_ulid=e.ulid)
    )
    updated = CompService.update_fields(
        ctx, s.ulid, CompScenarioUpdateInput(engagement_ulid=None)
    )
    assert updated.engagement_id is None


# ---------- compare ----------

def test_compare_deltas(db, ctx):
    _seed_baseline(db, base_gbp=200_000, cash_bonus_gbp=50_000, pension_pct=10.0)
    CompService.upsert(
        ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=250_000, cash_bonus_gbp=25_000),
    )
    out = CompService.compare(ctx)
    assert out["baseline"]["name"] == BASELINE_NAME
    assert len(out["scenarios"]) == 1
    deltas = out["scenarios"][0]["deltas"]
    assert deltas["base_gbp"] == {
        "baseline": 200_000, "scenario": 250_000, "delta_gbp": 50_000, "delta_pct": 25.0,
    }
    assert deltas["cash_bonus_gbp"]["delta_gbp"] == -25_000
    assert deltas["cash_bonus_gbp"]["delta_pct"] == -50.0
    # baseline pension 20k vs scenario 0
    assert deltas["pension_value_gbp"]["delta_gbp"] == -20_000
    # baseline total 200k+50k+20k pension = 270k; scenario total 275k
    assert deltas["total_gbp"]["delta_gbp"] == 5_000


def test_compare_pct_none_when_baseline_zero(db, ctx):
    _seed_baseline(db)  # all-null placeholder baseline
    CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=250_000))
    deltas = CompService.compare(ctx)["scenarios"][0]["deltas"]
    assert deltas["base_gbp"]["delta_gbp"] == 250_000
    assert deltas["base_gbp"]["delta_pct"] is None


def test_compare_default_excludes_baseline_and_deleted(db, ctx):
    _seed_baseline(db)
    CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    gone = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer B"))
    CompService.soft_delete(ctx, gone.ulid)
    out = CompService.compare(ctx)
    assert [s["name"] for s in out["scenarios"]] == ["Offer A"]


def test_compare_explicit_baseline_override(db, ctx):
    _seed_baseline(db, base_gbp=200_000)
    a = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A", base_gbp=250_000))
    b = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer B", base_gbp=260_000))
    out = CompService.compare(ctx, scenario_ulids=[b.ulid], baseline_ulid=a.ulid)
    assert out["baseline"]["ulid"] == a.ulid
    assert out["scenarios"][0]["deltas"]["base_gbp"]["delta_gbp"] == 10_000


def test_compare_without_baseline_raises(db, ctx):
    with pytest.raises(NotFoundError):
        CompService.compare(ctx)


def test_compare_unknown_scenario_raises(db, ctx):
    _seed_baseline(db)
    with pytest.raises(NotFoundError):
        CompService.compare(ctx, scenario_ulids=["01AAAAAAAAAAAAAAAAAAAAAAAA"])


# ---------- baseline swap / delete / restore ----------

def test_set_baseline_swaps_atomically(db, ctx):
    old = _seed_baseline(db)
    new = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    CompService.set_baseline(ctx, new.ulid)
    assert comp_repo.get_baseline(db).ulid == new.ulid
    assert comp_repo.get_scenario_by_ulid(db, old.ulid).is_baseline is False


def test_delete_refuses_baseline(db, ctx):
    b = _seed_baseline(db)
    with pytest.raises(ValidationError):
        CompService.soft_delete(ctx, b.ulid)


def test_delete_and_restore_roundtrip(db, ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    CompService.soft_delete(ctx, s.ulid)
    assert comp_repo.get_scenario_by_ulid(db, s.ulid).deleted_at is not None
    assert len(_audit_rows(db, "delete")) == 1
    restored = CompService.restore(ctx, s.ulid)
    assert restored.deleted_at is None
    assert len(_audit_rows(db, "restore")) == 1


def test_restore_name_conflict_raises(db, ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    CompService.soft_delete(ctx, s.ulid)
    CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))  # new live row, same name
    with pytest.raises(ConflictError):
        CompService.restore(ctx, s.ulid)


def test_restore_never_resurrects_second_baseline(db, ctx):
    old = _seed_baseline(db)
    new = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    CompService.set_baseline(ctx, new.ulid)
    # soft-delete the demoted row, flag it baseline again in the deleted state,
    # then restore: the live baseline must win.
    CompService.soft_delete(ctx, old.ulid)
    db.execute(
        "UPDATE compensation_scenarios SET is_baseline = 1 WHERE ulid = ?", (old.ulid,)
    )
    restored = CompService.restore(ctx, old.ulid)
    assert restored.is_baseline is False
    assert comp_repo.get_baseline(db).ulid == new.ulid


# ---------- owner gate (Rule 18) — reads included ----------

def test_bot_role_forbidden_everywhere(db, ctx, bot_ctx):
    s = CompService.upsert(ctx, UpsertCompScenarioInput(name="Offer A"))
    _seed_baseline(db)
    calls = [
        lambda: CompService.list(bot_ctx),
        lambda: CompService.get_by_ulid(bot_ctx, s.ulid),
        lambda: CompService.compare(bot_ctx),
        lambda: CompService.upsert(bot_ctx, UpsertCompScenarioInput(name="X")),
        lambda: CompService.update_fields(
            bot_ctx, s.ulid, CompScenarioUpdateInput(base_gbp=1)
        ),
        lambda: CompService.set_baseline(bot_ctx, s.ulid),
        lambda: CompService.soft_delete(bot_ctx, s.ulid),
        lambda: CompService.restore(bot_ctx, s.ulid),
    ]
    for call in calls:
        with pytest.raises(ForbiddenRoleError):
            call()
    denied = db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action = 'denied'"
    ).fetchone()[0]
    assert denied == len(calls)
