"""ProgrammeService — Rule 16 RAG thresholds + reciprocity suggestion."""
from __future__ import annotations

from datetime import date

from src.models import (
    AdvanceStageInput,
    EngagementStage,
    RagStatus,
    UpsertEngagementInput,
    UpsertMilestoneInput,
    UpsertOrgInput,
)
from src.repository import partners as partners_repo
from src.repository import firms as firms_repo
from src.models import FirmTier, RelationshipState
from src.services import ServiceContext
from src.services.engagements_service import EngagementsService
from src.services.orgs_service import OrgsService
from src.services.programme_service import ProgrammeService


def _ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="system", role="owner")


def _warm_partners(db, n: int) -> None:
    firm = firms_repo.get_firm_by_name(db, "TML") or firms_repo.insert_firm(
        db, name="TML", tier=FirmTier.specialist, region="London")
    existing = len(partners_repo.list_partners_by_firm(db, firm.id))
    for i in range(n):
        partners_repo.insert_partner(db, firm_id=firm.id, name=f"P{existing + i}",
                                     relationship_state=RelationshipState.warm)


def _engagement_at(db, stage: str, title: str) -> None:
    ctx = _ctx(db)
    org = OrgsService.upsert(ctx, UpsertOrgInput(name=f"Org-{title}", scale_band="fortune_500"))
    e = EngagementsService.upsert(ctx, UpsertEngagementInput(org_ulid=org.ulid, role_title=title, role_type="cmo"))
    # walk forward to the target stage
    order = ["surfaced", "exploratory", "formal", "final", "offer", "decision"]
    for s in order[1:order.index(stage) + 1]:
        EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage(s)))


def test_seed_rag_thresholds(db):
    ctx = _ctx(db)
    assert ProgrammeService._seed_rag(ctx).rag == RagStatus.red  # 0 warm
    _warm_partners(db, 3)
    assert ProgrammeService._seed_rag(ctx).rag == RagStatus.amber  # 3-4
    _warm_partners(db, 2)  # now 5 total
    assert ProgrammeService._seed_rag(ctx).rag == RagStatus.green  # >=5


def test_run_rag_thresholds(db):
    ctx = _ctx(db)
    assert ProgrammeService._run_rag(ctx).rag == RagStatus.red
    _engagement_at(db, "formal", "CMO-A")
    assert ProgrammeService._run_rag(ctx).rag == RagStatus.amber  # 1
    _engagement_at(db, "formal", "CMO-B")
    assert ProgrammeService._run_rag(ctx).rag == RagStatus.green  # >=2


def test_close_rag_and_target_at_risk(db):
    ctx = _ctx(db)
    status = ProgrammeService.status(ctx)
    close = next(p for p in status.phases if p.phase == "close")
    assert close.rag == RagStatus.red  # nothing at offer/decision
    assert status.target_at_risk is True
    _engagement_at(db, "offer", "CMO-Offer")
    status2 = ProgrammeService.status(ctx)
    close2 = next(p for p in status2.phases if p.phase == "close")
    assert close2.rag == RagStatus.green
    assert status2.target_at_risk is False


def test_offer_flips_close_milestone(db):
    ctx = _ctx(db)
    ProgrammeService.upsert_milestone(ctx, UpsertMilestoneInput(
        phase="close", label="Offer in hand", target_date=date(2027, 3, 24)))
    _engagement_at(db, "offer", "CMO-Flip")
    ms = [m for m in ProgrammeService.list_milestones(ctx) if m.phase.value == "close"][0]
    assert ms.status.value == "done"


def test_reciprocity_suggestion(db):
    ctx = _ctx(db)
    firm = firms_repo.insert_firm(db, name="Firm", tier=FirmTier.specialist, region="London")
    partner = partners_repo.insert_partner(db, firm_id=firm.id, name="Jane")
    org = OrgsService.upsert(ctx, UpsertOrgInput(name="OrgR", scale_band="fortune_500"))
    e = EngagementsService.upsert(ctx, UpsertEngagementInput(
        org_ulid=org.ulid, role_title="CMO", role_type="cmo", source_partner_ulid=partner.ulid))
    advanced = EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.exploratory))
    suggestion = ProgrammeService.reciprocity_suggestion(ctx, advanced)
    assert suggestion is not None and "Jane" in suggestion


def test_days_to_target_uses_env(db, monkeypatch):
    monkeypatch.setenv("ARTEMIDE_PROGRAMME_TARGET_DATE", "2099-01-01")
    assert ProgrammeService.days_to_target() > 0
