"""BoardEvaluationService — the weighted six-dimension board-offer framework.

Pure, deterministic scoring (analogous to fit_service): a fixed-weight sum on
the native 1–5 scale, with hard disqualifiers that force a 'pass' verdict (R2).
Weights are FIXED by the brief, so they live here as a code constant (unlike
fit_service, where weights live in a tunable profile). Owner-only on every
method; no search-index, no outbox — board data stays out of both.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..models import (
    AuditAction,
    BoardEvaluationRecord,
    BoardEvaluationResult,
    BoardOppEventType,
    BoardVerdict,
    SetBoardEvaluationInput,
)
from ..repository import board_evaluations as evaluations_repo
from ..repository import board_opportunities as opportunities_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError

# Fixed dimension weights (percentages, sum to 100).
BOARD_EVAL_WEIGHTS: dict[str, int] = {
    "chair_board_quality": 25,
    "mandate_contribution_fit": 25,
    "governance_health_risk": 20,
    "time_conflict_cost": 15,
    "brand_portfolio_value": 10,
    "terms": 5,
}

# Canonical hard-disqualifier keys (R2). Any ticked key forces verdict=pass.
BOARD_HARD_DISQUALIFIERS: set[str] = {
    "unclearable_sp_conflict",
    "dominant_chair_or_factional_board",
    "decorative_seat",
    "unmanaged_governance_risk",
    "inadequate_do_indemnification",
    "performative_visibility_demanded",
    "weak_transformation_ambition",
}

# Verdict bands on the 1–5 weighted scale (only reached when not force-passed).
_PROCEED_THRESHOLD = 4.0
_CAUTION_THRESHOLD = 3.0

_SCORE_COLUMNS = (
    "score_chair_board_quality", "score_mandate_contribution_fit",
    "score_governance_health_risk", "score_time_conflict_cost",
    "score_brand_portfolio_value", "score_terms",
)


def compute_board_evaluation(
    scores: dict[str, int], hard_disqualifiers: list[str]
) -> BoardEvaluationResult:
    """Pure weighted evaluation. DB-free so it is trivially unit-testable.

    `scores` is keyed by dimension (e.g. 'chair_board_quality') with 1–5 values.
    """
    total_weight = sum(BOARD_EVAL_WEIGHTS.values()) or 1
    dimensions: dict[str, dict[str, Any]] = {}
    weighted_sum = 0.0
    for dim, weight in BOARD_EVAL_WEIGHTS.items():
        raw = scores[dim]
        contribution = raw * weight
        weighted_sum += contribution
        dimensions[dim] = {
            "raw": raw,
            "weight": weight,
            "contribution": round(contribution / total_weight, 2),
        }

    weighted_total = round(weighted_sum / total_weight, 2)
    forced_pass = bool(hard_disqualifiers)

    if forced_pass:
        verdict = BoardVerdict.pass_
    elif weighted_total >= _PROCEED_THRESHOLD:
        verdict = BoardVerdict.proceed
    elif weighted_total >= _CAUTION_THRESHOLD:
        verdict = BoardVerdict.proceed_with_caution
    else:
        verdict = BoardVerdict.pass_

    breakdown: dict[str, Any] = {
        "weighted_total": weighted_total,
        "forced_pass": forced_pass,
        "hard_disqualifiers": list(hard_disqualifiers),
        "dimensions": dimensions,
    }
    return BoardEvaluationResult(
        weighted_total=weighted_total,
        verdict=verdict,
        forced_pass=forced_pass,
        breakdown=breakdown,
    )


class BoardEvaluationService:

    @staticmethod
    def get_by_opportunity_ulid(ctx: ServiceContext, opportunity_ulid: str) -> BoardEvaluationRecord | None:
        assert_owner(ctx, operation="read board evaluation")
        opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, opportunity_ulid)
        if opp is None:
            raise NotFoundError(f"board opportunity not found: {opportunity_ulid}")
        return evaluations_repo.get_by_opportunity(ctx.conn, opp.id)

    @staticmethod
    def set_evaluation(ctx: ServiceContext, data: SetBoardEvaluationInput) -> BoardEvaluationRecord:
        assert_owner(ctx, operation="set board evaluation")
        unknown = [d for d in data.hard_disqualifiers if d not in BOARD_HARD_DISQUALIFIERS]
        if unknown:
            raise ValidationError(f"unknown hard disqualifier(s): {', '.join(unknown)}")
        with transaction(ctx.conn):
            opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, data.opportunity_ulid)
            if opp is None:
                raise NotFoundError(f"board opportunity not found: {data.opportunity_ulid}")

            dim_scores = {dim: getattr(data, f"score_{dim}") for dim in BOARD_EVAL_WEIGHTS}
            result = compute_board_evaluation(dim_scores, data.hard_disqualifiers)

            score_columns = {col: getattr(data, col) for col in _SCORE_COLUMNS}
            evaluation = evaluations_repo.upsert_by_opportunity(
                ctx.conn,
                opportunity_id=opp.id,
                scores=score_columns,
                weighted_total=result.weighted_total,
                hard_disqualifiers=data.hard_disqualifiers,
                firo_b_fit_notes=data.firo_b_fit_notes,
                verdict=result.verdict,
            )
            opportunities_repo.set_evaluation(
                ctx.conn, opp.id, result.weighted_total, result.verdict
            )
            opportunities_repo.insert_log(
                ctx.conn, opportunity_id=opp.id, event_date=date.today(),
                event_type=BoardOppEventType.evaluation,
                summary=f"verdict {result.verdict.value} (total {result.weighted_total})",
            )
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_opportunity",
                entity_ulid=opp.ulid,
                after={
                    "eval_weighted_total": result.weighted_total,
                    "eval_verdict": result.verdict.value,
                    "forced_pass": result.forced_pass,
                },
            )
            return evaluation

    @staticmethod
    def compare(ctx: ServiceContext, opportunity_ulids: list[str]) -> dict[str, Any]:
        """Side-by-side evaluations across live opportunities (R: comparison view)."""
        assert_owner(ctx, operation="compare board evaluations")
        out: list[dict[str, Any]] = []
        for ulid in opportunity_ulids:
            opp = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid)
            if opp is None:
                raise NotFoundError(f"board opportunity not found: {ulid}")
            evaluation = evaluations_repo.get_by_opportunity(ctx.conn, opp.id)
            entry: dict[str, Any] = {
                "opportunity_ulid": opp.ulid,
                "organisation": opp.organisation,
                "stage": opp.stage.value,
                "interest": opp.interest.value,
                "weighted_total": opp.eval_weighted_total,
                "verdict": opp.eval_verdict,
                "scores": None,
                "hard_disqualifiers": [],
            }
            if evaluation is not None:
                entry["scores"] = {
                    col: getattr(evaluation, col) for col in _SCORE_COLUMNS
                }
                entry["hard_disqualifiers"] = evaluation.hard_disqualifiers
            out.append(entry)
        return {"weights": dict(BOARD_EVAL_WEIGHTS), "opportunities": out}
