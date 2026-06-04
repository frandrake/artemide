"""Events outbox repository — append-only event source (Rule 19)."""
from __future__ import annotations

import sqlite3

from ..models import EventOutboxRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, event_type, entity_type, entity_ulid, payload, "
    "created_at, delivered_at, delivery_attempts"
)


def _row_to_record(row: sqlite3.Row) -> EventOutboxRecord:
    return EventOutboxRecord.model_validate(dict(row))


def insert_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    entity_type: str,
    entity_ulid: str,
    payload: str | None = None,
    ulid: str | None = None,
) -> EventOutboxRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO events_outbox (ulid, event_type, entity_type, entity_ulid, payload) "
        "VALUES (?, ?, ?, ?, ?)",
        (ulid_value, event_type, entity_type, entity_ulid, payload),
    )
    row = conn.execute(f"SELECT {_COLUMNS} FROM events_outbox WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_record(row)


def get_by_ulid(conn: sqlite3.Connection, ulid: str) -> EventOutboxRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM events_outbox WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def list_undelivered(conn: sqlite3.Connection, limit: int = 50, attempt_cap: int | None = None) -> list[EventOutboxRecord]:
    clauses = ["delivered_at IS NULL"]
    params: list = []
    if attempt_cap is not None:
        clauses.append("delivery_attempts < ?")
        params.append(attempt_cap)
    params.append(limit)
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM events_outbox WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at ASC LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def mark_delivered(conn: sqlite3.Connection, ulid: str) -> bool:
    cur = conn.execute(
        "UPDATE events_outbox SET delivered_at = CURRENT_TIMESTAMP "
        "WHERE ulid = ? AND delivered_at IS NULL",
        (ulid,),
    )
    return cur.rowcount > 0


def increment_attempts(conn: sqlite3.Connection, ulid: str) -> None:
    conn.execute(
        "UPDATE events_outbox SET delivery_attempts = delivery_attempts + 1 WHERE ulid = ?",
        (ulid,),
    )


def bump_undelivered_attempts(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "UPDATE events_outbox SET delivery_attempts = delivery_attempts + 1 "
        "WHERE delivered_at IS NULL"
    )
    return cur.rowcount


def delete_delivered_before(conn: sqlite3.Connection, *, older_than_days: int) -> int:
    """Prune already-delivered events older than the retention window. Undelivered
    events are never removed (they still need a consumer). Returns rows deleted."""
    cur = conn.execute(
        "DELETE FROM events_outbox "
        "WHERE delivered_at IS NOT NULL AND delivered_at < datetime('now', ?)",
        (f"-{int(older_than_days)} days",),
    )
    return cur.rowcount


def count_undelivered(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM events_outbox WHERE delivered_at IS NULL").fetchone()
    return int(row[0])


def count_past_cap(conn: sqlite3.Connection, attempt_cap: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM events_outbox WHERE delivered_at IS NULL AND delivery_attempts >= ?",
        (attempt_cap,),
    ).fetchone()
    return int(row[0])


def oldest_undelivered(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT created_at FROM events_outbox WHERE delivered_at IS NULL "
        "ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    return str(row[0]) if row else None
