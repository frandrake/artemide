"""OutboxService — append-only events for n8n consumers (Rule 19).

Emit is best-effort and must never block or fail the originating mutation.
Consumers dedupe on events_outbox.ulid (at-least-once). The sweep increments
delivery_attempts and surfaces events past the attempt cap in Settings.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any

from ..models import EventOutboxRecord, OutboxHealth
from ..repository import outbox as outbox_repo
from . import ServiceContext

log = logging.getLogger("artemide.outbox")


def _attempt_cap() -> int:
    try:
        return int(os.environ.get("ARTEMIDE_OUTBOX_ATTEMPT_CAP", "10"))
    except ValueError:
        return 10


def _enabled() -> bool:
    return (os.environ.get("ARTEMIDE_OUTBOX_ENABLED", "true") or "").lower() in {"1", "true", "yes", "on"}


def _retention_days() -> int:
    try:
        return int(os.environ.get("ARTEMIDE_OUTBOX_RETENTION_DAYS", "30"))
    except ValueError:
        return 30


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


class OutboxService:

    @staticmethod
    def emit(
        ctx: ServiceContext,
        *,
        event_type: str,
        entity_type: str,
        entity_ulid: str,
        payload: dict[str, Any] | None = None,
    ) -> EventOutboxRecord | None:
        """Best-effort: append an event. Swallows all errors so a failure here
        can never roll back or block the mutation that triggered it."""
        if not _enabled():
            return None
        try:
            payload_json = json.dumps(payload, default=_json_default) if payload is not None else None
            return outbox_repo.insert_event(
                ctx.conn,
                event_type=event_type,
                entity_type=entity_type,
                entity_ulid=entity_ulid,
                payload=payload_json,
            )
        except Exception as e:  # pragma: no cover - defensive
            log.warning("outbox emit failed (%s/%s): %s", event_type, entity_ulid, e)
            return None

    @staticmethod
    def list_undelivered(ctx: ServiceContext, limit: int = 50) -> list[EventOutboxRecord]:
        return outbox_repo.list_undelivered(ctx.conn, limit=limit)

    @staticmethod
    def mark_delivered(ctx: ServiceContext, ulid: str) -> bool:
        return outbox_repo.mark_delivered(ctx.conn, ulid)

    @staticmethod
    def sweep(conn: sqlite3.Connection) -> int:
        """Increment delivery_attempts on every still-undelivered event. Safe to
        run repeatedly. Returns the number of events bumped. Events past the cap
        remain undelivered and are surfaced via health()."""
        return outbox_repo.bump_undelivered_attempts(conn)

    @staticmethod
    def prune(conn: sqlite3.Connection, *, older_than_days: int | None = None) -> int:
        """Delete delivered events older than the retention window so the
        append-only table doesn't grow unbounded. Undelivered events are kept."""
        days = older_than_days if older_than_days is not None else _retention_days()
        return outbox_repo.delete_delivered_before(conn, older_than_days=days)

    @staticmethod
    def health(ctx: ServiceContext) -> OutboxHealth:
        cap = _attempt_cap()
        oldest = outbox_repo.oldest_undelivered(ctx.conn)
        age = None
        if oldest is not None:
            row = ctx.conn.execute(
                "SELECT CAST((julianday('now') - julianday(?)) * 86400 AS INTEGER)", (oldest,)
            ).fetchone()
            age = int(row[0]) if row and row[0] is not None else None
        return OutboxHealth(
            undelivered=outbox_repo.count_undelivered(ctx.conn),
            oldest_undelivered_age_seconds=age,
            past_attempt_cap=outbox_repo.count_past_cap(ctx.conn, cap),
        )
