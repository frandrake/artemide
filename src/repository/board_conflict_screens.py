"""board_conflict_screen repository (1:1 with opportunity) — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import BoardConflictScreenRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, opportunity_id, is_sp_competitor, result, checked_date, notes, "
    "created_at, updated_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardConflictScreenRecord:
    return BoardConflictScreenRecord.model_validate(dict(row))


def get_by_opportunity(conn: sqlite3.Connection, opportunity_id: int) -> BoardConflictScreenRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_conflict_screen WHERE opportunity_id = ?",
        (opportunity_id,),
    ).fetchone()
    return _row_to_record(row) if row else None


def get_by_opportunity_ids(
    conn: sqlite3.Connection, ids: list[int]
) -> dict[int, BoardConflictScreenRecord]:
    unique = list({i for i in ids if i is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_conflict_screen WHERE opportunity_id IN ({placeholders})",
        unique,
    ).fetchall()
    return {r["opportunity_id"]: _row_to_record(r) for r in rows}


def upsert_by_opportunity(
    conn: sqlite3.Connection,
    *,
    opportunity_id: int,
    is_sp_competitor: bool,
    result: Any,
    checked_date: date | None,
    notes: str | None,
    ulid: str | None = None,
) -> BoardConflictScreenRecord:
    existing = get_by_opportunity(conn, opportunity_id)
    if existing is None:
        ulid_value = ulid or new_ulid()
        conn.execute(
            "INSERT INTO board_conflict_screen (ulid, opportunity_id, is_sp_competitor, "
            "result, checked_date, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (ulid_value, opportunity_id, 1 if is_sp_competitor else 0, _val(result),
             checked_date, notes),
        )
    else:
        conn.execute(
            "UPDATE board_conflict_screen SET is_sp_competitor = ?, result = ?, "
            "checked_date = ?, notes = ? WHERE opportunity_id = ?",
            (1 if is_sp_competitor else 0, _val(result), checked_date, notes, opportunity_id),
        )
    return get_by_opportunity(conn, opportunity_id)  # type: ignore[return-value]
