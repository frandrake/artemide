"""board_target repository — the single-row NED-search goal."""
from __future__ import annotations

import sqlite3
from datetime import date

from ..models import BoardTargetRecord
from ..ulid_helpers import new_ulid

_COLUMNS = "id, ulid, seats_target, target_date, notes, created_at, updated_at"


def get_target(conn: sqlite3.Connection) -> BoardTargetRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_target LIMIT 1").fetchone()
    return BoardTargetRecord.model_validate(dict(row)) if row else None


def upsert_target(
    conn: sqlite3.Connection,
    *,
    seats_target: int,
    target_date: date | None = None,
    notes: str | None = None,
) -> BoardTargetRecord:
    existing = get_target(conn)
    if existing is None:
        conn.execute(
            "INSERT INTO board_target (ulid, seats_target, target_date, notes) "
            "VALUES (?, ?, ?, ?)",
            (new_ulid(), seats_target, target_date, notes),
        )
    else:
        conn.execute(
            "UPDATE board_target SET seats_target = ?, target_date = ?, notes = ? WHERE id = ?",
            (seats_target, target_date, notes, existing.id),
        )
    target = get_target(conn)
    assert target is not None
    return target
