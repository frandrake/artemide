"""OutboxService — Rule 19: at-least-once, dedupe by ulid, attempt cap, sweep."""
from __future__ import annotations

from src.repository import outbox as outbox_repo
from src.services import ServiceContext
from src.services.outbox_service import OutboxService


def _ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="system", role="owner")


def test_emit_appends_event(db):
    ctx = _ctx(db)
    ev = OutboxService.emit(ctx, event_type="engagement.surfaced", entity_type="engagement",
                            entity_ulid="01ENG0000000000000000001", payload={"a": 1})
    assert ev is not None
    undelivered = OutboxService.list_undelivered(ctx)
    assert len(undelivered) == 1
    assert undelivered[0].event_type == "engagement.surfaced"


def test_mark_delivered_is_idempotent(db):
    ctx = _ctx(db)
    ev = OutboxService.emit(ctx, event_type="message.approved", entity_type="message",
                            entity_ulid="01MSG0000000000000000001")
    assert OutboxService.mark_delivered(ctx, ev.ulid) is True
    # second ack on the same ulid is a no-op (consumers dedupe on ulid)
    assert OutboxService.mark_delivered(ctx, ev.ulid) is False
    assert OutboxService.list_undelivered(ctx) == []


def test_sweep_increments_attempts_and_is_repeatable(db):
    ctx = _ctx(db)
    ev = OutboxService.emit(ctx, event_type="touch.overdue", entity_type="partner",
                            entity_ulid="01PTR0000000000000000001")
    OutboxService.sweep(db)
    OutboxService.sweep(db)
    refreshed = outbox_repo.get_by_ulid(db, ev.ulid)
    assert refreshed.delivery_attempts == 2
    # delivered events are not bumped
    OutboxService.mark_delivered(ctx, ev.ulid)
    OutboxService.sweep(db)
    assert outbox_repo.get_by_ulid(db, ev.ulid).delivery_attempts == 2


def test_health_reports_past_cap(db, monkeypatch):
    monkeypatch.setenv("ARTEMIDE_OUTBOX_ATTEMPT_CAP", "3")
    ctx = _ctx(db)
    OutboxService.emit(ctx, event_type="x", entity_type="e", entity_ulid="01A0000000000000000000001")
    for _ in range(3):
        OutboxService.sweep(db)
    health = OutboxService.health(ctx)
    assert health.undelivered == 1
    assert health.past_attempt_cap == 1


def test_emit_disabled_returns_none(db, monkeypatch):
    monkeypatch.setenv("ARTEMIDE_OUTBOX_ENABLED", "false")
    ctx = _ctx(db)
    assert OutboxService.emit(ctx, event_type="x", entity_type="e", entity_ulid="01B0000000000000000000001") is None
    assert OutboxService.list_undelivered(ctx) == []
