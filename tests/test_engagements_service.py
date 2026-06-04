"""EngagementsService — Rule 14 stage guard, logging, outbox emission."""
from __future__ import annotations

import pytest

from src.models import AdvanceStageInput, CloseEngagementInput, ClosedReason, EngagementStage, UpsertEngagementInput
from src.repository import engagements as engagements_repo
from src.repository import outbox as outbox_repo
from src.services import ServiceContext
from src.services.engagements_service import EngagementsService
from src.services.exceptions import InvalidStateTransitionError, ValidationError
from src.services.orgs_service import OrgsService
from src.models import UpsertOrgInput


def _ctx(db, role="owner"):
    return ServiceContext(conn=db, actor="FF", transport="system", role=role)


def _make_engagement(db):
    ctx = _ctx(db)
    OrgsService.upsert(ctx, UpsertOrgInput(name="Acme Global", scale_band="fortune_500"))
    org = OrgsService.get_by_name(ctx, "Acme Global")
    e = EngagementsService.upsert(ctx, UpsertEngagementInput(
        org_ulid=org.ulid, role_title="Group CMO", role_type="cmo",
    ))
    return ctx, e


def test_upsert_emits_surfaced_event(db):
    ctx, e = _make_engagement(db)
    events = outbox_repo.list_undelivered(db)
    assert any(ev.event_type == "engagement.surfaced" and ev.entity_ulid == e.ulid for ev in events)


def test_advance_forward_ok_and_logs(db):
    ctx, e = _make_engagement(db)
    updated = EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.exploratory, summary="intro call"))
    assert updated.stage == EngagementStage.exploratory
    log = engagements_repo.list_log(db, e.id)
    assert log and log[0].event_type.value == "stage_change"
    assert log[0].from_stage == "surfaced" and log[0].to_stage == "exploratory"


def test_advance_backward_rejected(db):
    ctx, e = _make_engagement(db)
    EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.formal))
    with pytest.raises(InvalidStateTransitionError):
        EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.exploratory))


def test_advance_same_stage_rejected(db):
    ctx, e = _make_engagement(db)
    with pytest.raises(InvalidStateTransitionError):
        EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.surfaced))


def test_advance_emits_stage_changed(db):
    ctx, e = _make_engagement(db)
    EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.exploratory))
    events = outbox_repo.list_undelivered(db)
    assert any(ev.event_type == "engagement.stage_changed" for ev in events)


def test_advance_to_closed_requires_reason(db):
    """Closing via advance must carry a closed_reason — never leave it NULL."""
    ctx, e = _make_engagement(db)
    with pytest.raises(ValidationError):
        EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.closed))
    # nothing committed: still in the opening stage
    assert EngagementsService.get_by_ulid(ctx, e.ulid).stage == EngagementStage.surfaced


def test_advance_to_closed_then_cannot_advance(db):
    ctx, e = _make_engagement(db)
    closed = EngagementsService.advance_stage(
        ctx, e.ulid,
        AdvanceStageInput(to_stage=EngagementStage.closed, closed_reason=ClosedReason.withdrew, summary="paused"),
    )
    assert closed.stage == EngagementStage.closed
    # routed through close() → reason is persisted, not NULL
    assert closed.closed_reason == ClosedReason.withdrew
    with pytest.raises(InvalidStateTransitionError):
        EngagementsService.advance_stage(ctx, e.ulid, AdvanceStageInput(to_stage=EngagementStage.exploratory))


def test_close_sets_reason_and_logs(db):
    ctx, e = _make_engagement(db)
    closed = EngagementsService.close(ctx, e.ulid, CloseEngagementInput(closed_reason=ClosedReason.lapsed, summary="went cold"))
    assert closed.stage == EngagementStage.closed
    assert closed.closed_reason == ClosedReason.lapsed
    log = engagements_repo.list_log(db, e.id)
    assert log[0].to_stage == "closed"


def test_bot_cannot_soft_delete_engagement(db):
    ctx, e = _make_engagement(db)
    bot = _ctx(db, role="bot")
    from src.services.exceptions import ForbiddenRoleError
    with pytest.raises(ForbiddenRoleError):
        EngagementsService.soft_delete(bot, e.ulid)
