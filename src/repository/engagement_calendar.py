"""Engagement calendar repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import EngagementCalendarRecord
from ..ulid_helpers import new_ulid


_COLUMNS = (
    "id, ulid, firm_id, partner_id, due_date, title, description, "
    "status, track, created_at"
)


def _row_to_record(row: sqlite3.Row) -> EngagementCalendarRecord:
    return EngagementCalendarRecord.model_validate(dict(row))


def insert_engagement(
    conn: sqlite3.Connection,
    *,
    firm_id: int | None,
    partner_id: int | None,
    due_date: date | str,
    title: str,
    description: str | None = None,
    status: str = "not_set",
    track: str | None = None,
    ulid: str | None = None,
) -> EngagementCalendarRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO engagement_calendar "
        "(ulid, firm_id, partner_id, due_date, title, description, status, track) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, firm_id, partner_id, str(due_date), title, description, status, track),
    )
    return get_engagement_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_engagement_by_id(conn: sqlite3.Connection, eng_id: int) -> EngagementCalendarRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM engagement_calendar WHERE id = ?", (eng_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def get_engagement_by_ulid(conn: sqlite3.Connection, ulid: str) -> EngagementCalendarRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM engagement_calendar WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_engagements(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    track: str | None = None,
    due_before: date | str | None = None,
    due_after: date | str | None = None,
    partner_id: int | None = None,
    firm_id: int | None = None,
) -> list[EngagementCalendarRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if track is not None:
        clauses.append("track = ?")
        params.append(track)
    if due_before is not None:
        clauses.append("due_date <= ?")
        params.append(str(due_before))
    if due_after is not None:
        clauses.append("due_date >= ?")
        params.append(str(due_after))
    if partner_id is not None:
        clauses.append("partner_id = ?")
        params.append(partner_id)
    if firm_id is not None:
        clauses.append("firm_id = ?")
        params.append(firm_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM engagement_calendar {where} ORDER BY due_date ASC, id ASC",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_FIELDS = {"status", "due_date", "title", "description", "track"}


def update_engagement_fields(
    conn: sqlite3.Connection, eng_id: int, fields: dict[str, Any]
) -> EngagementCalendarRecord | None:
    updates = {
        k: (v.value if hasattr(v, "value") else (str(v) if isinstance(v, date) else v))
        for k, v in fields.items() if k in _ALLOWED_FIELDS
    }
    if not updates:
        return get_engagement_by_id(conn, eng_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE engagement_calendar SET {assignments} WHERE id = ?",
        (*updates.values(), eng_id),
    )
    return get_engagement_by_id(conn, eng_id)


def count_engagements_by_status(
    conn: sqlite3.Connection,
    *,
    due_after: date | str,
    due_before: date | str,
) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) as n FROM engagement_calendar "
        "WHERE due_date >= ? AND due_date <= ? GROUP BY status",
        (str(due_after), str(due_before)),
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}
