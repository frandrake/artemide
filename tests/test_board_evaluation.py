"""Pure board offer-evaluation engine — weighting + R2 disqualifier override."""
from __future__ import annotations

from src.services.board_evaluation_service import (
    BOARD_EVAL_WEIGHTS,
    compute_board_evaluation,
)

ALL = {
    "chair_board_quality": 5,
    "mandate_contribution_fit": 5,
    "governance_health_risk": 5,
    "time_conflict_cost": 5,
    "brand_portfolio_value": 5,
    "terms": 5,
}


def _scores(**overrides):
    s = dict(ALL)
    s.update(overrides)
    return s


def test_weights_sum_to_100():
    assert sum(BOARD_EVAL_WEIGHTS.values()) == 100


def test_all_fives_is_five_and_proceeds():
    r = compute_board_evaluation(ALL, [])
    assert r.weighted_total == 5.0
    assert r.verdict.value == "proceed"
    assert r.forced_pass is False


def test_weighting_is_deterministic():
    # 4,5,3,4,3,4 → 25*4+25*5+20*3+15*4+10*3+5*4 = 395 / 100 = 3.95
    r = compute_board_evaluation(
        _scores(chair_board_quality=4, governance_health_risk=3, time_conflict_cost=4,
                brand_portfolio_value=3, terms=4),
        [],
    )
    assert r.weighted_total == 3.95
    assert r.verdict.value == "proceed_with_caution"


def test_low_scores_pass_band():
    r = compute_board_evaluation(_scores(**{k: 2 for k in ALL}), [])
    assert r.weighted_total == 2.0
    assert r.verdict.value == "pass"
    assert r.forced_pass is False


def test_r2_disqualifier_forces_pass_regardless_of_score():
    r = compute_board_evaluation(ALL, ["unclearable_sp_conflict"])
    # Top scores but a hard disqualifier → forced pass, total preserved.
    assert r.weighted_total == 5.0
    assert r.verdict.value == "pass"
    assert r.forced_pass is True


def test_breakdown_has_every_dimension_with_weight():
    r = compute_board_evaluation(ALL, [])
    dims = r.breakdown["dimensions"]
    assert set(dims) == set(BOARD_EVAL_WEIGHTS)
    for dim, weight in BOARD_EVAL_WEIGHTS.items():
        assert dims[dim]["weight"] == weight
        assert dims[dim]["raw"] == 5
