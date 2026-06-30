"""board_interaction repository — pure data access (append-only activity log)."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import BoardInteractionRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, interaction_date, interaction_type, linked_entity_type, "
    "linked_entity_ulid, summary, next_action, due_date, created_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardInteractionRecord:
    return BoardInteractionRecord.model_validate(dict(row))


def insert_interaction(
    conn: sqlite3.Connection,
    *,
    interaction_date: date,
    interaction_type: Any,
    linked_entity_type: Any,
    linked_entity_ulid: str,
    summary: str | None = None,
    next_action: str | None = None,
    due_date: date | None = None,
    ulid: str | None = None,
) -> BoardInteractionRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_interaction (ulid, interaction_date, interaction_type, "
        "linked_entity_type, linked_entity_ulid, summary, next_action, due_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, interaction_date, _val(interaction_type), _val(linked_entity_type),
         linked_entity_ulid, summary, next_action, due_date),
    )
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_interaction WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _row_to_record(row)


def list_by_entity(
    conn: sqlite3.Connection, linked_entity_type: Any, linked_entity_ulid: str
) -> list[BoardInteractionRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_interaction "
        "WHERE linked_entity_type = ? AND linked_entity_ulid = ? "
        "ORDER BY interaction_date DESC, id DESC",
        (_val(linked_entity_type), linked_entity_ulid),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def list_due(conn: sqlite3.Connection, *, due_on_or_before: date) -> list[BoardInteractionRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_interaction "
        "WHERE due_date IS NOT NULL AND due_date <= ? "
        "ORDER BY due_date ASC, id ASC",
        (due_on_or_before,),
    ).fetchall()
    return [_row_to_record(r) for r in rows]
