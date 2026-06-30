"""Board domain service rules — R1 (advisory), R3 (trail), R5, conflict mapping,
owner-only gating, and the no-bleed invariants that keep the domain separate."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.models import (
    AdvanceBoardStageInput,
    RecordConflictScreenInput,
    SetBoardEvaluationInput,
    UpsertBoardContactInput,
    UpsertBoardFirmInput,
    UpsertBoardOpportunityInput,
)
from src.repository import firms as exec_firms_repo
from src.services import ServiceContext
from src.services.audit_service import AuditService
from src.services.board_contacts_service import BoardContactsService
from src.services.board_evaluation_service import BoardEvaluationService
from src.services.board_conflict_service import BoardConflictService
from src.services.board_firms_service import BoardFirmsService
from src.services.board_opportunities_service import BoardOpportunitiesService
from src.services.exceptions import ForbiddenRoleError, InvalidStateTransitionError


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="cli")


@pytest.fixture
def bot_ctx(db):
    return ServiceContext(conn=db, actor="n8n", transport="rest", role="bot")


def _opp(ctx, organisation="Acme plc"):
    return BoardOpportunitiesService.upsert(
        ctx, UpsertBoardOpportunityInput(
            organisation=organisation, board_type="listed_ftse350", role="ned",
        ),
    )


# ---------- R1: advisory conflict gate ----------

def test_advance_into_conflict_screen_has_no_warning(ctx):
    o = _opp(ctx)
    updated, warnings = BoardOpportunitiesService.advance_stage(
        ctx, o.ulid, AdvanceBoardStageInput(to_stage="conflict_screen"))
    assert updated.stage.value == "conflict_screen"
    assert warnings == []


def test_advance_past_conflict_screen_uncleared_warns_but_allows(ctx):
    o = _opp(ctx)
    BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(to_stage="conflict_screen"))
    updated, warnings = BoardOpportunitiesService.advance_stage(
        ctx, o.ulid, AdvanceBoardStageInput(to_stage="chair_meeting"))
    # Advisory: the move is permitted, but a warning is surfaced.
    assert updated.stage.value == "chair_meeting"
    assert len(warnings) == 1
    assert "conflict" in warnings[0].lower()


def test_cleared_conflict_removes_warning(ctx):
    o = _opp(ctx)
    BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(to_stage="conflict_screen"))
    BoardConflictService.record_screen(ctx, RecordConflictScreenInput(
        opportunity_ulid=o.ulid, is_sp_competitor=False, result="pass"))
    updated, warnings = BoardOpportunitiesService.advance_stage(
        ctx, o.ulid, AdvanceBoardStageInput(to_stage="chair_meeting"))
    assert updated.stage.value == "chair_meeting"
    assert warnings == []


def test_stage_machine_is_forward_only(ctx):
    o = _opp(ctx)
    BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(to_stage="chair_meeting"))
    with pytest.raises(InvalidStateTransitionError):
        BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(to_stage="surfaced"))


# ---------- conflict screen → conflict_cleared mapping ----------

@pytest.mark.parametrize("result,expected", [("pass", "yes"), ("fail", "no"), ("pending", "pending")])
def test_conflict_result_maps_to_cleared(ctx, result, expected):
    o = _opp(ctx)
    BoardConflictService.record_screen(ctx, RecordConflictScreenInput(
        opportunity_ulid=o.ulid, is_sp_competitor=(result == "fail"), result=result))
    refreshed = BoardOpportunitiesService.get_by_ulid(ctx, o.ulid)
    assert refreshed.conflict_cleared.value == expected


# ---------- R3: stage audit trail (board_opportunity_log + audit_log) ----------

def test_advance_writes_dual_trail(ctx, db):
    o = _opp(ctx)
    BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(
        to_stage="conflict_screen", summary="screening"))
    log_rows = db.execute(
        "SELECT * FROM board_opportunity_log WHERE opportunity_id = ? AND event_type = 'stage_change'",
        (o.id,)).fetchall()
    assert len(log_rows) == 1
    assert log_rows[0]["to_stage"] == "conflict_screen"
    audit_rows = db.execute(
        "SELECT * FROM audit_log WHERE entity_type = 'board_opportunity' AND action = 'stage'"
    ).fetchall()
    assert len(audit_rows) == 1


# ---------- R5: contact-move flag (verify_before_send) ----------

@pytest.mark.parametrize("days_ago,expected", [(100, True), (10, False), (None, True)])
def test_verify_before_send(ctx, days_ago, expected):
    last = None if days_ago is None else date.today() - timedelta(days=days_ago)
    c = BoardContactsService.upsert(ctx, UpsertBoardContactInput(
        name="Jane Chair", relationship="warm", last_contact_date=last))
    payload = BoardContactsService.to_payload(ctx, c)
    assert payload["verify_before_send"] is expected


# ---------- R2 (service): evaluation persists rollup + forced pass ----------

def test_set_evaluation_persists_rollup_and_forced_pass(ctx):
    o = _opp(ctx)
    BoardEvaluationService.set_evaluation(ctx, SetBoardEvaluationInput(
        opportunity_ulid=o.ulid,
        score_chair_board_quality=5, score_mandate_contribution_fit=5,
        score_governance_health_risk=5, score_time_conflict_cost=5,
        score_brand_portfolio_value=5, score_terms=5,
        hard_disqualifiers=["decorative_seat"]))
    refreshed = BoardOpportunitiesService.get_by_ulid(ctx, o.ulid)
    assert refreshed.eval_weighted_total == 5.0
    assert refreshed.eval_verdict == "pass"  # forced by disqualifier


def test_unknown_disqualifier_rejected(ctx):
    from src.services.exceptions import ValidationError
    o = _opp(ctx)
    with pytest.raises(ValidationError):
        BoardEvaluationService.set_evaluation(ctx, SetBoardEvaluationInput(
            opportunity_ulid=o.ulid,
            score_chair_board_quality=3, score_mandate_contribution_fit=3,
            score_governance_health_risk=3, score_time_conflict_cost=3,
            score_brand_portfolio_value=3, score_terms=3,
            hard_disqualifiers=["not_a_real_key"]))


# ---------- owner-only gating ----------

def test_bot_blocked_on_board_reads_and_writes(bot_ctx):
    with pytest.raises(ForbiddenRoleError):
        BoardFirmsService.list(bot_ctx)
    with pytest.raises(ForbiddenRoleError):
        BoardFirmsService.upsert(bot_ctx, UpsertBoardFirmInput(name="X"))


# ---------- no-bleed: board never enters search / outbox / exec views ----------

def test_board_does_not_bleed(ctx, db):
    BoardFirmsService.upsert(ctx, UpsertBoardFirmInput(
        name="ZZZ Board Partners", firm_type="boutique", geography=["UK"], tier=1))
    o = _opp(ctx, organisation="ZZZ Holdings plc")
    BoardOpportunitiesService.advance_stage(ctx, o.ulid, AdvanceBoardStageInput(to_stage="conflict_screen"))

    # never indexed into the shared search corpus
    assert db.execute(
        "SELECT COUNT(*) FROM search_index WHERE entity_type LIKE 'board%'"
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM search_index WHERE primary_text LIKE '%ZZZ%'"
    ).fetchone()[0] == 0
    # never emitted to the external event stream
    assert db.execute(
        "SELECT COUNT(*) FROM events_outbox WHERE entity_type LIKE 'board%'"
    ).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM events_outbox").fetchone()[0] == 0
    # exec firm directory untouched, and the audit report sees no board entities
    assert len(exec_firms_repo.list_firms(db)) == 0
    report = AuditService.generate_report(ctx)
    names = [e.firm_name for e in report.primary_tier_coverage + report.specialist_tier_coverage]
    assert all("ZZZ" not in n for n in names)
