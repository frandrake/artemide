"""Programme milestones repository."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import ProgrammeMilestoneRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, phase, label, target_date, status, metric_note, created_at, updated_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> ProgrammeMilestoneRecord:
    return ProgrammeMilestoneRecord.model_validate(dict(row))


def insert_milestone(
    conn: sqlite3.Connection,
    *,
    phase: Any,
    label: str,
    target_date: date,
    status: Any = "pending",
    metric_note: str | None = None,
    ulid: str | None = None,
) -> ProgrammeMilestoneRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO programme_milestones (ulid, phase, label, target_date, status, metric_note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ulid_value, _val(phase), label, target_date, _val(status) or "pending", metric_note),
    )
    return get_milestone_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_milestone_by_id(conn: sqlite3.Connection, milestone_id: int) -> ProgrammeMilestoneRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM programme_milestones WHERE id = ?", (milestone_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_milestone_by_ulid(conn: sqlite3.Connection, ulid: str) -> ProgrammeMilestoneRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM programme_milestones WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_milestone_by_phase(conn: sqlite3.Connection, phase: Any) -> ProgrammeMilestoneRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM programme_milestones WHERE phase = ? ORDER BY target_date ASC LIMIT 1",
        (_val(phase),),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_milestones(conn: sqlite3.Connection) -> list[ProgrammeMilestoneRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM programme_milestones ORDER BY target_date ASC"
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_MILESTONE_FIELDS = {"phase", "label", "target_date", "status", "metric_note"}


def update_milestone_fields(conn: sqlite3.Connection, milestone_id: int, fields: dict[str, Any]) -> ProgrammeMilestoneRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_MILESTONE_FIELDS}
    if not updates:
        return get_milestone_by_id(conn, milestone_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE programme_milestones SET {assignments} WHERE id = ?",
        (*updates.values(), milestone_id),
    )
    return get_milestone_by_id(conn, milestone_id)


def set_status(conn: sqlite3.Connection, milestone_id: int, status: Any) -> None:
    conn.execute(
        "UPDATE programme_milestones SET status = ? WHERE id = ?",
        (_val(status), milestone_id),
    )
