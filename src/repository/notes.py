"""Notes repository — free-form notes on firms/partners."""
from __future__ import annotations

import sqlite3

from ..models import NoteEntityType, NoteRecord
from ..ulid_helpers import new_ulid


_COLUMNS = "id, ulid, entity_type, entity_id, body, created_at"


def _row_to_record(row: sqlite3.Row) -> NoteRecord:
    return NoteRecord.model_validate(dict(row))


def insert_note(
    conn: sqlite3.Connection,
    *,
    entity_type: NoteEntityType,
    entity_id: str,
    body: str,
    ulid: str | None = None,
) -> NoteRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO notes (ulid, entity_type, entity_id, body) VALUES (?, ?, ?, ?)",
        (ulid_value, entity_type.value, entity_id, body),
    )
    row = conn.execute(f"SELECT {_COLUMNS} FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_record(row)


def get_note_by_ulid(conn: sqlite3.Connection, ulid: str) -> NoteRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM notes WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def list_notes_by_entity(
    conn: sqlite3.Connection, entity_type: NoteEntityType, entity_id: str
) -> list[NoteRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM notes WHERE entity_type = ? AND entity_id = ? "
        f"ORDER BY created_at DESC, id DESC",
        (entity_type.value, entity_id),
    ).fetchall()
    return [_row_to_record(r) for r in rows]
