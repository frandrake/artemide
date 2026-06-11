"""Interviews repository — pure data access.

Metadata reads (`list_by_engagement`) deliberately omit the `transcript` column
so large bodies are not loaded for timeline views; `get_interview_by_*` returns
the full record including the transcript.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import InterviewRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, engagement_id, engagement_log_id, interview_date, round, "
    "format, panel, summary, transcript, transcript_source, "
    "created_at, updated_at, deleted_at"
)

# Same columns minus the (potentially large) transcript body — used by list
# views so timelines never haul transcripts into memory.
_META_COLUMNS = (
    "id, ulid, engagement_id, engagement_log_id, interview_date, round, "
    "format, panel, summary, transcript_source, "
    "created_at, updated_at, deleted_at"
)

_ALLOWED_UPDATE_FIELDS = {"interview_date", "round", "format", "panel", "summary"}


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> InterviewRecord:
    return InterviewRecord.model_validate(dict(row))


def insert_interview(
    conn: sqlite3.Connection,
    *,
    engagement_id: int,
    interview_date: date,
    round: str | None = None,
    format: Any = None,
    panel: str | None = None,
    summary: str | None = None,
    transcript: str | None = None,
    transcript_source: Any = None,
    engagement_log_id: int | None = None,
    ulid: str | None = None,
) -> InterviewRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO interviews (ulid, engagement_id, engagement_log_id, "
        "interview_date, round, format, panel, summary, transcript, transcript_source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, engagement_id, engagement_log_id, interview_date, round,
            _val(format), panel, summary, transcript, _val(transcript_source),
        ),
    )
    return get_interview_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def set_engagement_log_id(conn: sqlite3.Connection, interview_id: int, log_id: int) -> None:
    conn.execute(
        "UPDATE interviews SET engagement_log_id = ? WHERE id = ?",
        (log_id, interview_id),
    )


def get_interview_by_id(conn: sqlite3.Connection, interview_id: int) -> InterviewRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def get_interview_by_ulid(conn: sqlite3.Connection, ulid: str) -> InterviewRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM interviews WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_by_engagement(conn: sqlite3.Connection, engagement_id: int) -> list[InterviewRecord]:
    """Metadata only — the transcript column is not selected. The returned
    records carry transcript=None regardless of stored content."""
    rows = conn.execute(
        f"SELECT {_META_COLUMNS} FROM interviews "
        "WHERE engagement_id = ? AND deleted_at IS NULL "
        "ORDER BY interview_date DESC, id DESC",
        (engagement_id,),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def set_transcript(
    conn: sqlite3.Connection, interview_id: int, transcript: str, source: Any
) -> None:
    conn.execute(
        "UPDATE interviews SET transcript = ?, transcript_source = ? WHERE id = ?",
        (transcript, _val(source), interview_id),
    )


def update_fields(
    conn: sqlite3.Connection, interview_id: int, fields: dict[str, Any]
) -> InterviewRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_UPDATE_FIELDS}
    if not updates:
        return get_interview_by_id(conn, interview_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE interviews SET {assignments} WHERE id = ?",
        (*updates.values(), interview_id),
    )
    return get_interview_by_id(conn, interview_id)


def soft_delete(conn: sqlite3.Connection, interview_id: int) -> None:
    conn.execute(
        "UPDATE interviews SET deleted_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND deleted_at IS NULL",
        (interview_id,),
    )


def restore(conn: sqlite3.Connection, interview_id: int) -> None:
    conn.execute("UPDATE interviews SET deleted_at = NULL WHERE id = ?", (interview_id,))
