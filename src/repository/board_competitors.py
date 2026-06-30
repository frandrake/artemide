"""board_competitor repository (R4 S&P competitor reference list) — pure data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import BoardCompetitorRecord
from ..ulid_helpers import new_ulid

_COLUMNS = "id, ulid, name, notes, active, created_at, updated_at"


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardCompetitorRecord:
    return BoardCompetitorRecord.model_validate(dict(row))


def insert_competitor(
    conn: sqlite3.Connection,
    *,
    name: str,
    notes: str | None = None,
    active: bool = True,
    ulid: str | None = None,
) -> BoardCompetitorRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_competitor (ulid, name, notes, active) VALUES (?, ?, ?, ?)",
        (ulid_value, name, notes, 1 if active else 0),
    )
    return get_competitor_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_competitor_by_id(conn: sqlite3.Connection, competitor_id: int) -> BoardCompetitorRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_competitor WHERE id = ?", (competitor_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_competitor_by_ulid(conn: sqlite3.Connection, ulid: str) -> BoardCompetitorRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_competitor WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_competitor_by_name(conn: sqlite3.Connection, name: str) -> BoardCompetitorRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_competitor WHERE name = ?", (name,)).fetchone()
    return _row_to_record(row) if row else None


def list_competitors(
    conn: sqlite3.Connection, *, active_only: bool = False
) -> list[BoardCompetitorRecord]:
    where = "WHERE active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_competitor {where} ORDER BY name ASC"
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_COMPETITOR_FIELDS = {"name", "notes", "active"}


def update_competitor_fields(
    conn: sqlite3.Connection, competitor_id: int, fields: dict[str, Any]
) -> BoardCompetitorRecord | None:
    updates: dict[str, Any] = {}
    for k, v in fields.items():
        if k not in _ALLOWED_COMPETITOR_FIELDS:
            continue
        updates[k] = (1 if v else 0) if k == "active" else _val(v)
    if not updates:
        return get_competitor_by_id(conn, competitor_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE board_competitor SET {assignments} WHERE id = ?",
        (*updates.values(), competitor_id),
    )
    return get_competitor_by_id(conn, competitor_id)
