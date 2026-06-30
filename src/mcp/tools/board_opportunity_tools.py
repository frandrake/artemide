"""MCP tools — board opportunities, the conflict gate and the evaluation."""
from __future__ import annotations

from ...api._serde import to_response, to_response_list
from ...models import (
    AdvanceBoardStageInput,
    BoardConflictCleared,
    BoardOppInterest,
    BoardStage,
    RecordConflictScreenInput,
    SetBoardEvaluationInput,
    UpsertBoardOpportunityInput,
)
from ...repository import board_conflict_screens as screens_repo
from ...repository import board_evaluations as evaluations_repo
from ...repository import board_opportunities as opportunities_repo
from ...services.board_conflict_service import BoardConflictService
from ...services.board_evaluation_service import (
    BOARD_EVAL_WEIGHTS,
    BoardEvaluationService,
    compute_board_evaluation,
)
from ...services.board_opportunities_service import BoardOpportunitiesService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def board_upsert_opportunity(payload: UpsertBoardOpportunityInput) -> dict:
    """Create or update a board/NED opportunity (a specific seat)."""
    with tool_session("board_upsert_opportunity") as (conn, ctx):
        try:
            o = BoardOpportunitiesService.upsert(ctx, payload)
            return {"ok": True, "opportunity": BoardOpportunitiesService.to_payload(ctx, o)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_list_opportunities(
    stage: BoardStage | None = None,
    interest: BoardOppInterest | None = None,
    conflict_cleared: BoardConflictCleared | None = None,
    sort: str | None = None,
) -> dict:
    """List board opportunities (filters: stage, interest, conflict_cleared; sort: date_surfaced|eval)."""
    with tool_session("board_list_opportunities") as (conn, ctx):
        try:
            items = BoardOpportunitiesService.list(
                ctx, stage=stage, interest=interest, conflict_cleared=conflict_cleared, sort=sort
            )
            return {"ok": True, "opportunities": [BoardOpportunitiesService.to_payload(ctx, o) for o in items]}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_get_opportunity(opportunity_ulid: str) -> dict:
    """Get a board opportunity with its conflict screen, evaluation, log and interactions."""
    with tool_session("board_get_opportunity") as (conn, ctx):
        try:
            o = BoardOpportunitiesService.get_by_ulid(ctx, opportunity_ulid)
            payload = BoardOpportunitiesService.to_payload(ctx, o)
            screen = screens_repo.get_by_opportunity(ctx.conn, o.id)
            payload["conflict_screen"] = to_response(screen, extra_exclude={"opportunity_id"}) if screen else None
            evaluation = evaluations_repo.get_by_opportunity(ctx.conn, o.id)
            payload["evaluation"] = to_response(evaluation, extra_exclude={"opportunity_id"}) if evaluation else None
            payload["log"] = to_response_list(
                opportunities_repo.list_log(ctx.conn, o.id), extra_exclude={"opportunity_id"}
            )
            return {"ok": True, "opportunity": payload}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_advance_opportunity(
    opportunity_ulid: str, to_stage: BoardStage, summary: str | None = None
) -> dict:
    """Advance a board opportunity forward. Advisory R1: advancing past
    conflict_screen while conflict_cleared != 'yes' returns a warning (it does
    not block)."""
    with tool_session("board_advance_opportunity") as (conn, ctx):
        try:
            o, warnings = BoardOpportunitiesService.advance_stage(
                ctx, opportunity_ulid, AdvanceBoardStageInput(to_stage=to_stage, summary=summary)
            )
            return {
                "ok": True,
                "opportunity": BoardOpportunitiesService.to_payload(ctx, o),
                "warnings": warnings,
            }
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_record_conflict_screen(payload: RecordConflictScreenInput) -> dict:
    """Record the conflict-of-interest screen; maps result→conflict_cleared on the opportunity."""
    with tool_session("board_record_conflict_screen") as (conn, ctx):
        try:
            screen = BoardConflictService.record_screen(ctx, payload)
            o = BoardOpportunitiesService.get_by_ulid(ctx, payload.opportunity_ulid)
            return {
                "ok": True,
                "conflict_screen": to_response(screen, extra_exclude={"opportunity_id"}),
                "conflict_cleared": o.conflict_cleared.value,
            }
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_set_evaluation(payload: SetBoardEvaluationInput) -> dict:
    """Score the six-dimension board offer framework. Returns weighted_total,
    verdict and the per-dimension breakdown. Any hard disqualifier forces
    verdict='pass' (R2)."""
    with tool_session("board_set_evaluation") as (conn, ctx):
        try:
            evaluation = BoardEvaluationService.set_evaluation(ctx, payload)
            dim_scores = {dim: getattr(payload, f"score_{dim}") for dim in BOARD_EVAL_WEIGHTS}
            result = compute_board_evaluation(dim_scores, payload.hard_disqualifiers)
            return {
                "ok": True,
                "evaluation": to_response(evaluation, extra_exclude={"opportunity_id"}),
                "weighted_total": result.weighted_total,
                "verdict": result.verdict.value,
                "forced_pass": result.forced_pass,
                "breakdown": result.breakdown,
            }
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_compare_evaluations(opportunity_ulids: list[str]) -> dict:
    """Side-by-side weighted scores and verdicts across live board opportunities."""
    with tool_session("board_compare_evaluations") as (conn, ctx):
        try:
            return {"ok": True, "comparison": BoardEvaluationService.compare(ctx, opportunity_ulids)}
        except Exception as e:
            return error_response(e)
