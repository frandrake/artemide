"""Retention sweeps — the outbox and the idempotency cache stay bounded.

Both are pruned from the in-process sweep loop (src/app.py). These cover the
repository/service behaviour the loop relies on.
"""
from __future__ import annotations

from src.api.deps import prune_expired_idempotency_keys, store_idempotent_response
from src.repository import outbox as outbox_repo
from src.services import ServiceContext
from src.services.outbox_service import OutboxService


def _ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="system", role="owner")


def test_prune_removes_old_delivered_events_only(db):
    ctx = _ctx(db)
    old = OutboxService.emit(ctx, event_type="x", entity_type="e", entity_ulid="01OLD0000000000000000001")
    recent = OutboxService.emit(ctx, event_type="x", entity_type="e", entity_ulid="01NEW0000000000000000001")
    undelivered = OutboxService.emit(ctx, event_type="x", entity_type="e", entity_ulid="01UND0000000000000000001")
    OutboxService.mark_delivered(ctx, old.ulid)
    OutboxService.mark_delivered(ctx, recent.ulid)
    # Backdate the old delivery past the retention window.
    db.execute(
        "UPDATE events_outbox SET delivered_at = datetime('now', '-60 days') WHERE ulid = ?",
        (old.ulid,),
    )

    assert OutboxService.prune(db, older_than_days=30) == 1
    assert outbox_repo.get_by_ulid(db, old.ulid) is None            # old + delivered → pruned
    assert outbox_repo.get_by_ulid(db, recent.ulid) is not None     # within window → kept
    assert outbox_repo.get_by_ulid(db, undelivered.ulid) is not None  # never delivered → always kept


def test_prune_expired_idempotency_keys(db):
    db.execute(
        "INSERT INTO idempotency_keys (key, response_body, response_status, expires_at) "
        "VALUES ('stale', '{}', 200, datetime('now', '-1 hour'))"
    )
    store_idempotent_response(db, "fresh", {"ok": True}, 200)  # expires 24h out

    assert prune_expired_idempotency_keys(db) == 1
    remaining = {r[0] for r in db.execute("SELECT key FROM idempotency_keys").fetchall()}
    assert remaining == {"fresh"}
