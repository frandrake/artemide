"""Pure persistence for the redacted, side-effect-free notification queue."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, notification_type, priority, fingerprint, payload, not_before, "
    "expires_at, queued_at, sent_at"
)


def insert_or_get(
    conn: sqlite3.Connection, *, notification_type: str, priority: str,
    fingerprint: str, payload: str, not_before: str, expires_at: str, queued_at: str,
) -> tuple[dict[str, Any], bool]:
    existing = conn.execute(
        f"SELECT {_COLUMNS} FROM notification_dispatch WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    if existing is not None:
        return dict(existing), False
    ulid = new_ulid()
    cur = conn.execute(
        "INSERT INTO notification_dispatch "
        "(ulid, notification_type, priority, fingerprint, payload, not_before, expires_at, queued_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ulid, notification_type, priority, fingerprint, payload, not_before, expires_at, queued_at),
    )
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM notification_dispatch WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return dict(row), True


def get_by_ulid(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM notification_dispatch WHERE ulid = ?", (ulid,)
    ).fetchone()
    return dict(row) if row is not None else None


def list_eligible(conn: sqlite3.Connection, *, now: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM notification_dispatch "
        "WHERE sent_at IS NULL AND not_before <= ? AND expires_at > ? "
        "ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, queued_at, id "
        "LIMIT ?",
        (now, now, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def mark_sent(conn: sqlite3.Connection, *, ulid: str, sent_at: str) -> bool:
    cur = conn.execute(
        "UPDATE notification_dispatch SET sent_at = ? "
        "WHERE ulid = ? AND sent_at IS NULL AND not_before <= ? AND expires_at > ?",
        (sent_at, ulid, sent_at, sent_at),
    )
    return cur.rowcount > 0
