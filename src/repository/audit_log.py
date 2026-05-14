"""Audit log repository — append-only."""
from __future__ import annotations

import sqlite3

from ..models import AuditAction, AuditLogRecord, AuditTransport
from ..ulid_helpers import new_ulid


_COLUMNS = "id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp"


def _row_to_record(row: sqlite3.Row) -> AuditLogRecord:
    return AuditLogRecord.model_validate(dict(row))


def insert_audit_entry(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    action: AuditAction,
    actor: str,
    transport: AuditTransport,
    payload: str | None = None,
    ulid: str | None = None,
) -> AuditLogRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO audit_log (ulid, entity_type, entity_id, action, actor, transport, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, entity_type, entity_id, action.value, actor, transport.value, payload),
    )
    row = conn.execute(f"SELECT {_COLUMNS} FROM audit_log WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_record(row)


def get_audit_by_ulid(conn: sqlite3.Connection, ulid: str) -> AuditLogRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM audit_log WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def list_audit_entries_by_entity(
    conn: sqlite3.Connection, entity_type: str, entity_id: str, *, limit: int = 100
) -> list[AuditLogRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM audit_log WHERE entity_type = ? AND entity_id = ? "
        f"ORDER BY timestamp DESC, id DESC LIMIT ?",
        (entity_type, entity_id, int(limit)),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def list_recent_audit_entries(conn: sqlite3.Connection, *, limit: int = 100) -> list[AuditLogRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM audit_log ORDER BY timestamp DESC, id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def list_audit_entries_by_actor(
    conn: sqlite3.Connection, actor: str, *, limit: int = 100
) -> list[AuditLogRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM audit_log WHERE actor = ? ORDER BY timestamp DESC, id DESC LIMIT ?",
        (actor, int(limit)),
    ).fetchall()
    return [_row_to_record(r) for r in rows]
