"""Value calendar repository — one row per (year, quarter)."""
from __future__ import annotations

import sqlite3

from ..models import CalendarStatus, ValueCalendarRecord
from ..ulid_helpers import new_ulid


_COLUMNS = "id, ulid, year, quarter, topic, status, created_at, updated_at"


def _row_to_record(row: sqlite3.Row) -> ValueCalendarRecord:
    return ValueCalendarRecord.model_validate(dict(row))


def upsert_quarter_topic(
    conn: sqlite3.Connection,
    *,
    year: int,
    quarter: int,
    topic: str | None,
    status: CalendarStatus | None = None,
) -> ValueCalendarRecord:
    existing = get_quarter_topic(conn, year=year, quarter=quarter)
    if existing is None:
        ulid_value = new_ulid()
        conn.execute(
            "INSERT INTO value_calendar (ulid, year, quarter, topic, status) VALUES (?, ?, ?, ?, ?)",
            (ulid_value, year, quarter, topic, (status or CalendarStatus.planned).value if topic else (status or CalendarStatus.not_set).value),
        )
    else:
        next_status = (status or existing.status).value
        conn.execute(
            "UPDATE value_calendar SET topic = ?, status = ? WHERE year = ? AND quarter = ?",
            (topic, next_status, year, quarter),
        )
    return get_quarter_topic(conn, year=year, quarter=quarter)  # type: ignore[return-value]


def get_quarter_topic(
    conn: sqlite3.Connection, *, year: int, quarter: int
) -> ValueCalendarRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM value_calendar WHERE year = ? AND quarter = ?",
        (year, quarter),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_quarter_topics(conn: sqlite3.Connection, year: int) -> list[ValueCalendarRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM value_calendar WHERE year = ? ORDER BY quarter",
        (year,),
    ).fetchall()
    return [_row_to_record(r) for r in rows]
