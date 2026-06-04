"""Tests for FitService (Rule 13) — hard-fail cap, comp distance, weights, neutrals."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.models import EngagementProfileRecord
from src.repository import engagement_profile as profile_repo
from src.repository import engagements as engagements_repo
from src.repository import orgs as orgs_repo
from src.services import ServiceContext
from src.services.fit_service import HARD_FAIL_CAP, NEUTRAL, FitService, compute_fit

_BASE_PROFILE = {
    "id": 1,
    "ulid": "01TESTPROFILE000000000001",
    "version": 1,
    "active": 1,
    "comp_base_floor_gbp": 250_000,
    "comp_total_target_gbp": 500_000,
    "accepted_role_types": ["cmo", "cmgo", "cco", "transformation"],
    "accepted_scale_bands": ["fortune_500", "global_equivalent"],
    "hard_exclusions": ["high_politics", "weak_transformation"],
    "weights": {
        "role_type": 20, "scale": 15, "comp": 20, "pertinence": 15,
        "geography": 10, "autonomy_signal": 10, "politics_signal": 10,
    },
    "created_at": datetime(2026, 1, 1),
}


def make_profile(**overrides) -> EngagementProfileRecord:
    data = {**_BASE_PROFILE, **overrides}
    return EngagementProfileRecord.model_validate(data)


def _score(**kwargs):
    defaults = dict(
        role_type="cmo", scale_band="fortune_500", comp_base_gbp=300_000,
        comp_total_gbp=500_000, pertinence_note="coherent move", tags=[],
        profile=make_profile(),
    )
    defaults.update(kwargs)
    return compute_fit(**defaults)


# ---------- hard filters ----------

def test_role_type_not_accepted_hard_fails_and_caps_at_39():
    r = _score(role_type="ned")  # 'ned' not in accepted_role_types
    assert r.hard_fail is True
    assert "role_type" in r.breakdown["failed_filters"]
    assert r.score <= HARD_FAIL_CAP


def test_scale_band_not_accepted_hard_fails():
    r = _score(scale_band="pe_backed")
    assert r.hard_fail is True
    assert "scale_band" in r.breakdown["failed_filters"]
    assert r.score <= HARD_FAIL_CAP


def test_comp_floor_breach_hard_fails():
    r = _score(comp_base_gbp=200_000)  # below £250k floor
    assert r.hard_fail is True
    assert "comp_floor" in r.breakdown["failed_filters"]


def test_hard_exclusion_tag_hard_fails():
    r = _score(tags=["high_politics"])
    assert r.hard_fail is True
    assert "hard_exclusion" in r.breakdown["failed_filters"]
    assert "high_politics" in r.breakdown["excluded_tags"]


def test_unknown_role_type_is_not_a_hard_fail():
    r = _score(role_type=None)
    assert r.hard_fail is False
    assert r.breakdown["dimensions"]["role_type"]["raw"] == NEUTRAL


# ---------- comp distance ----------

def test_comp_at_or_above_target_scores_100():
    p = make_profile(weights={"comp": 100})
    assert _score(comp_total_gbp=500_000, profile=p).breakdown["dimensions"]["comp"]["raw"] == 100
    assert _score(comp_total_gbp=600_000, profile=p).breakdown["dimensions"]["comp"]["raw"] == 100


def test_comp_half_target_scores_about_50():
    p = make_profile(weights={"comp": 100})
    raw = _score(comp_total_gbp=250_000, profile=p).breakdown["dimensions"]["comp"]["raw"]
    assert raw == 50


def test_comp_unknown_is_neutral():
    p = make_profile(weights={"comp": 100})
    assert _score(comp_total_gbp=None, profile=p).breakdown["dimensions"]["comp"]["raw"] == NEUTRAL


# ---------- weights ----------

def test_weighted_sum_matches_manual_calculation():
    # All dims known, with a low_politics tag for a high politics_signal.
    r = _score(tags=["high_autonomy", "low_politics"])
    # role_type 100*20 + scale 100*15 + comp 100*20 + pertinence 75*15
    # + geography 50*10 + autonomy 90*10 + politics 90*10 = 8925 / 100 = 89.25 -> 89
    assert r.score == 89
    assert r.hard_fail is False


def test_all_unknown_dimensions_score_neutral_50():
    p = make_profile()
    r = compute_fit(
        role_type=None, scale_band=None, comp_base_gbp=None, comp_total_gbp=None,
        pertinence_note=None, tags=[], profile=p,
    )
    assert r.hard_fail is False
    assert r.score == NEUTRAL
    for dim in r.breakdown["dimensions"].values():
        assert dim["raw"] == NEUTRAL


def test_unknown_weight_dimension_scores_neutral():
    # A weight key with no scorer falls back to neutral.
    p = make_profile(weights={"mystery_dimension": 100})
    r = _score(profile=p)
    assert r.score == NEUTRAL
    assert r.breakdown["dimensions"]["mystery_dimension"]["raw"] == NEUTRAL


# ---------- persistence (DB-backed) ----------

def test_rescore_persists_score_and_breakdown(db):
    profile_repo.insert_profile(
        db, version=1, active=True,
        comp_base_floor_gbp=250_000, comp_total_target_gbp=500_000,
        accepted_role_types=["cmo"], accepted_scale_bands=["fortune_500"],
        hard_exclusions=[], weights={"role_type": 50, "comp": 50},
    )
    org = orgs_repo.insert_org(db, name="Acme Global", scale_band="fortune_500",
                               pertinence_note="coherent")
    eng = engagements_repo.insert_engagement(
        db, org_id=org.id, role_title="Group CMO", role_type="cmo",
        comp_base_gbp=300_000, comp_total_gbp=500_000,
    )
    ctx = ServiceContext(conn=db, actor="FF", transport="system")
    result = FitService.rescore(ctx, eng)
    assert result.score == 100  # role_type 100*50 + comp 100*50 / 100
    reloaded = engagements_repo.get_engagement_by_id(db, eng.id)
    assert reloaded.fit_score == 100
    assert reloaded.fit_breakdown is not None and "dimensions" in reloaded.fit_breakdown


def test_rescore_all_counts_open_engagements(db):
    profile_repo.insert_profile(
        db, version=1, active=True,
        comp_base_floor_gbp=250_000, comp_total_target_gbp=500_000,
        accepted_role_types=["cmo"], accepted_scale_bands=["fortune_500"],
        hard_exclusions=[], weights={"role_type": 100},
    )
    org = orgs_repo.insert_org(db, name="Acme", scale_band="fortune_500")
    open_eng = engagements_repo.insert_engagement(db, org_id=org.id, role_title="CMO", role_type="cmo")
    closed_eng = engagements_repo.insert_engagement(db, org_id=org.id, role_title="CCO", role_type="cmo")
    engagements_repo.set_closed(db, closed_eng.id, "lapsed")
    ctx = ServiceContext(conn=db, actor="FF", transport="system")
    assert FitService.rescore_all(ctx) == 1  # only the open one


# ---------- profile input validation ----------

def test_fit_profile_input_rejects_degenerate_weights():
    from pydantic import ValidationError as PydanticValidationError

    from src.models import FitProfileInput

    base = dict(
        comp_base_floor_gbp=250_000,
        comp_total_target_gbp=500_000,
        accepted_role_types=["cmo"],
        accepted_scale_bands=["fortune_500"],
        hard_exclusions=[],
    )
    for bad in ({}, {"role_type": 0, "comp": 0}, {"role_type": -5, "comp": 5}):
        with pytest.raises(PydanticValidationError):
            FitProfileInput(**base, weights=bad)
    # a positive-sum, non-negative set still constructs
    assert FitProfileInput(**base, weights={"role_type": 100}).weights == {"role_type": 100}
