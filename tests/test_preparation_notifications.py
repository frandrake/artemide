"""Focused tests for immutable preparation packs and redacted notifications."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from src.services import ServiceContext
from src.services.exceptions import ConflictError, ForbiddenRoleError, ValidationError
from src.services.notification_service import NotificationService
from src.services.preparation_service import PreparationService


def _ctx(db, *, role="owner", actor="FF"):
    return ServiceContext(conn=db, actor=actor, transport="system", role=role)


def _source(label="Role specification"):
    return {
        "source_kind": "attachment",
        "source_ulid": "01HSOURCE000000000000000",
        "sha256": "a" * 64,
        "retrieved_at": "2026-07-21T09:00:00+00:00",
        "citation_label": label,
    }


def test_executive_pack_is_versioned_hashed_cited_and_content_immutable(db):
    ctx = _ctx(db)
    first = PreparationService.propose_executive(
        ctx,
        target_entity_type="engagement",
        target_entity_ulid="01HENGAGEMENT00000000000",
        content="# Preparation\nEvidence [role-spec].",
        sources=[_source("role-spec")],
        generated_by="agent",
        model="test-model",
        prompt_version="prep-v1",
    )
    second = PreparationService.propose_executive(
        ctx,
        target_entity_type="engagement",
        target_entity_ulid="01HENGAGEMENT00000000000",
        content="# Preparation v2\nMore evidence [role-spec].",
        sources=[_source("role-spec")],
        generated_by="agent",
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert first["status"] == "proposed"
    assert len(first["content_sha256"]) == 64
    assert first["sources"][0]["citation_label"] == "role-spec"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute(
            "UPDATE executive_preparation_pack SET content = 'tampered' WHERE ulid = ?",
            (first["ulid"],),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute(
            "DELETE FROM executive_preparation_pack_source WHERE pack_id = ?",
            (first["id"],),
        )


def test_pack_requires_provenance_and_confirmation_is_owner_only_and_supersedes(db):
    owner = _ctx(db)
    bot = _ctx(db, role="bot", actor="worker")
    with pytest.raises(ValidationError, match="source"):
        PreparationService.propose_executive(
            owner,
            target_entity_type="engagement",
            target_entity_ulid="01HENGAGEMENT00000000000",
            content="No citations",
            sources=[],
            generated_by="agent",
        )
    v1 = PreparationService.propose_executive(
        owner, target_entity_type="engagement", target_entity_ulid="01HENGAGEMENT00000000000",
        content="v1 [source]", sources=[_source("source")], generated_by="agent",
    )
    with pytest.raises(ForbiddenRoleError):
        PreparationService.propose_executive(
            bot,
            target_entity_type="engagement",
            target_entity_ulid="01HENGAGEMENT00000000000",
            content="v0 [source]",
            sources=[_source("source")],
            generated_by="agent",
        )
    with pytest.raises(ForbiddenRoleError):
        PreparationService.confirm_executive(bot, v1["ulid"])
    confirmed_v1 = PreparationService.confirm_executive(owner, v1["ulid"])
    assert confirmed_v1["status"] == "confirmed"
    assert confirmed_v1["confirmed_by"] == "FF"

    v2 = PreparationService.propose_executive(
        owner, target_entity_type="engagement", target_entity_ulid="01HENGAGEMENT00000000000",
        content="v2 [source]", sources=[_source("source")], generated_by="agent",
    )
    PreparationService.confirm_executive(owner, v2["ulid"])
    assert PreparationService.get_executive(owner, v1["ulid"])["status"] == "superseded"
    with pytest.raises(ConflictError):
        PreparationService.confirm_executive(owner, v1["ulid"])


def test_board_packs_are_owner_only_and_physically_separate_from_shared_surfaces(db):
    owner = _ctx(db)
    bot = _ctx(db, role="bot", actor="worker")
    before = {
        table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("attachments", "search_index", "events_outbox")
    }
    pack = PreparationService.propose_board(
        owner,
        board_opportunity_ulid="01HBOARDOPPORTUNITY000000",
        content="Confidential chair notes [public-source]",
        sources=[{
            "source_kind": "public_url", "public_url": "https://example.com/board",
            "sha256": "b" * 64, "retrieved_at": "2026-07-21T10:00:00Z",
            "citation_label": "public-source",
        }],
        generated_by="agent",
    )
    assert pack["version"] == 1
    assert db.execute("SELECT COUNT(*) FROM executive_preparation_pack").fetchone()[0] == 0
    after = {
        table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("attachments", "search_index", "events_outbox")
    }
    assert after == before
    with pytest.raises(ForbiddenRoleError):
        PreparationService.get_board(bot, pack["ulid"])
    with pytest.raises(ForbiddenRoleError):
        PreparationService.propose_board(
            bot, board_opportunity_ulid="x", content="x", sources=[_source()], generated_by="worker"
        )


def test_notification_quiet_hours_use_europe_london_and_0730_boundary(db):
    ctx = _ctx(db, role="bot", actor="worker")
    # 19:00 UTC is 20:00 Europe/London in July (BST): defer to 07:30 local.
    queued = NotificationService.queue(
        ctx, notification_type="action_due", priority="P2", dedupe_key="episode-evening",
        payload={"summary_code": "ACTION_DUE", "count": 1, "action_code": "OPEN_APP"},
        now=datetime(2026, 7, 21, 19, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc),
    )
    assert queued["not_before"] == "2026-07-22T06:30:00+00:00"
    assert NotificationService.list_eligible(
        ctx, now=datetime(2026, 7, 22, 6, 29, tzinfo=timezone.utc)
    ) == []
    assert [r["ulid"] for r in NotificationService.list_eligible(
        ctx, now=datetime(2026, 7, 22, 6, 30, tzinfo=timezone.utc)
    )] == [queued["ulid"]]


def test_notification_payload_is_redacted_side_effect_free_and_p1_is_deduplicated(db):
    ctx = _ctx(db, role="bot", actor="worker")
    now = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
    expiry = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)
    payload = {
        "summary_code": "OVERDUE_ACTIONS", "count": 3, "workstream": "executive",
        "person_name": "Sensitive Name", "compensation": "£500k", "message_body": "secret",
    }
    first = NotificationService.queue(
        ctx, notification_type="overdue_episode", priority="P1", dedupe_key="overdue:2026-07-21",
        payload=payload, now=now, expires_at=expiry,
    )
    duplicate = NotificationService.queue(
        ctx, notification_type="overdue_episode", priority="P1", dedupe_key="overdue:2026-07-21",
        payload={**payload, "count": 4}, now=now, expires_at=expiry,
    )

    assert duplicate["ulid"] == first["ulid"]
    assert db.execute("SELECT COUNT(*) FROM notification_dispatch").fetchone()[0] == 1
    stored = json.loads(first["payload"])
    assert stored == {"count": 3, "summary_code": "OVERDUE_ACTIONS", "workstream": "executive"}
    assert db.execute("SELECT COUNT(*) FROM events_outbox").fetchone()[0] == 0
    assert len(first["fingerprint"]) == 64


def test_notification_expiry_and_mark_sent_are_side_effect_free_and_idempotent(db):
    ctx = _ctx(db, role="bot", actor="worker")
    now = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
    row = NotificationService.queue(
        ctx, notification_type="review", priority="P3", dedupe_key="review:1",
        payload={"summary_code": "REVIEW", "count": 1}, now=now,
        expires_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
    )
    assert NotificationService.list_eligible(ctx, now=now)
    assert NotificationService.mark_sent(ctx, row["ulid"], sent_at=now) is True
    assert NotificationService.mark_sent(ctx, row["ulid"], sent_at=now) is False
    assert NotificationService.list_eligible(ctx, now=now) == []

    expired = NotificationService.queue(
        ctx, notification_type="review", priority="P3", dedupe_key="review:2",
        payload={"summary_code": "REVIEW", "count": 1}, now=now,
        expires_at=datetime(2026, 7, 21, 9, 1, tzinfo=timezone.utc),
    )
    assert NotificationService.list_eligible(
        ctx, now=datetime(2026, 7, 21, 9, 1, tzinfo=timezone.utc)
    ) == []
    assert expired["sent_at"] is None
