"""FitService — Rule 13 fit scoring against the active engagement_profile.

Pure, deterministic scoring: a hard-filter gate followed by a weighted soft
score. Weights live in the profile, so retuning needs no code change. Every
score carries its breakdown — no opaque numbers (a v1.2 non-goal).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models import EngagementProfileRecord, EngagementRecord, FitResult, OrganisationRecord
from ..repository import engagement_profile as profile_repo
from ..repository import engagements as engagements_repo
from ..repository import orgs as orgs_repo
from . import ServiceContext

# Canonical dimensions and the value used when a dimension cannot be evaluated.
NEUTRAL = 50
HARD_FAIL_CAP = 39


class ProfileMissingError(RuntimeError):
    """Raised when scoring is attempted with no active engagement_profile."""


def _clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def _score_role_type(role_type: str | None, accepted: list[str]) -> int:
    if not role_type:
        return NEUTRAL
    return 100 if role_type in accepted else 0


def _score_scale(scale_band: str | None, accepted: list[str]) -> int:
    if not scale_band:
        return NEUTRAL
    return 100 if scale_band in accepted else 0


def _score_comp(comp_total_gbp: int | None, target: int) -> int:
    if comp_total_gbp is None or target <= 0:
        return NEUTRAL
    if comp_total_gbp >= target:
        return 100
    return _clamp(comp_total_gbp / target * 100)


def _score_pertinence(pertinence_note: str | None) -> int:
    return 75 if (pertinence_note and pertinence_note.strip()) else NEUTRAL


def _score_from_tags(tags: set[str], positive: str, negative: str, *, inverse: bool = False) -> int:
    has_pos = positive in tags
    has_neg = negative in tags
    if has_pos and not has_neg:
        return 10 if inverse else 90
    if has_neg and not has_pos:
        return 90 if inverse else 10
    return NEUTRAL


def compute_fit(
    *,
    role_type: str | None,
    scale_band: str | None,
    comp_base_gbp: int | None,
    comp_total_gbp: int | None,
    pertinence_note: str | None,
    tags: list[str] | None,
    profile: EngagementProfileRecord,
) -> FitResult:
    """Pure fit computation. DB-free so it is trivially unit-testable."""
    tag_set = {t.strip().lower() for t in (tags or []) if t and t.strip()}

    # ---- Hard filters (gate) ----
    failed: list[str] = []
    if role_type and role_type not in profile.accepted_role_types:
        failed.append("role_type")
    if scale_band and scale_band not in profile.accepted_scale_bands:
        failed.append("scale_band")
    excluded_hits = sorted(tag_set & {t.lower() for t in profile.hard_exclusions})
    if excluded_hits:
        failed.append("hard_exclusion")
    if comp_base_gbp is not None and comp_base_gbp < profile.comp_base_floor_gbp:
        failed.append("comp_floor")
    hard_fail = bool(failed)

    # ---- Soft score (weighted) ----
    scorers: dict[str, int] = {
        "role_type": _score_role_type(role_type, profile.accepted_role_types),
        "scale": _score_scale(scale_band, profile.accepted_scale_bands),
        "comp": _score_comp(comp_total_gbp, profile.comp_total_target_gbp),
        "pertinence": _score_pertinence(pertinence_note),
        "geography": NEUTRAL,  # no geography signal yet → neutral
        "autonomy_signal": _score_from_tags(tag_set, "high_autonomy", "low_autonomy"),
        "politics_signal": _score_from_tags(tag_set, "high_politics", "low_politics", inverse=True),
    }

    weights = profile.weights
    total_weight = sum(weights.values()) or 1
    dimensions: dict[str, dict[str, Any]] = {}
    weighted_sum = 0.0
    for dim, weight in weights.items():
        raw = scorers.get(dim, NEUTRAL)  # unknown dimension → neutral 50
        contribution = raw * weight
        weighted_sum += contribution
        dimensions[dim] = {"raw": raw, "weight": weight, "contribution": round(contribution / total_weight, 2)}

    soft_score = _clamp(weighted_sum / total_weight)
    score = min(soft_score, HARD_FAIL_CAP) if hard_fail else soft_score

    breakdown: dict[str, Any] = {
        "soft_score": soft_score,
        "hard_fail": hard_fail,
        "failed_filters": failed,
        "excluded_tags": excluded_hits,
        "dimensions": dimensions,
        "profile_version": profile.version,
    }
    return FitResult(score=score, hard_fail=hard_fail, breakdown=breakdown)


class FitService:
    """Scores engagements against the active profile and persists the result."""

    @staticmethod
    def get_active_profile(conn: sqlite3.Connection) -> EngagementProfileRecord | None:
        return profile_repo.get_active_profile(conn)

    @staticmethod
    def _tags_for(engagement: EngagementRecord, org: OrganisationRecord | None) -> list[str]:
        """Tags driving hard-exclusion / signal dimensions are sourced from the
        org's external_refs JSON (`tags` key) plus the engagement fit_breakdown
        carry-over if present. Kept permissive — absence means neutral."""
        tags: list[str] = []
        if org and org.external_refs:
            try:
                refs = json.loads(org.external_refs)
                if isinstance(refs, dict) and isinstance(refs.get("tags"), list):
                    tags.extend(str(t) for t in refs["tags"])
            except (ValueError, TypeError):
                pass
        return tags

    @staticmethod
    def score(conn: sqlite3.Connection, engagement: EngagementRecord) -> FitResult:
        profile = profile_repo.get_active_profile(conn)
        if profile is None:
            raise ProfileMissingError("no active engagement_profile")
        org = orgs_repo.get_org_by_id(conn, engagement.org_id)
        result = compute_fit(
            role_type=engagement.role_type.value if engagement.role_type else None,
            scale_band=org.scale_band.value if (org and org.scale_band) else None,
            comp_base_gbp=engagement.comp_base_gbp,
            comp_total_gbp=engagement.comp_total_gbp,
            pertinence_note=org.pertinence_note if org else None,
            tags=FitService._tags_for(engagement, org),
            profile=profile,
        )
        return result

    @staticmethod
    def rescore(ctx: ServiceContext, engagement: EngagementRecord) -> FitResult:
        """Score and persist fit_score/fit_breakdown back onto the engagement."""
        result = FitService.score(ctx.conn, engagement)
        engagements_repo.set_fit(
            ctx.conn, engagement.id, result.score, json.dumps(result.breakdown)
        )
        return result

    @staticmethod
    def rescore_all(ctx: ServiceContext) -> int:
        """Rescore every open (non-closed, non-deleted) engagement. Returns count."""
        open_engagements = [
            e for e in engagements_repo.list_engagements(ctx.conn)
            if e.stage.value != "closed"
        ]
        for engagement in open_engagements:
            FitService.rescore(ctx, engagement)
        return len(open_engagements)
