"""board_opportunity + board_opportunity_log repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import BoardOpportunityLogRecord, BoardOpportunityRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, organisation, board_type, role, source_firm_id, source_text, "
    "chair_contact_id, date_surfaced, stage, conflict_cleared, interest, "
    "next_step, notes, eval_weighted_total, eval_verdict, "
    "created_at, updated_at, deleted_at"
)

_LOG_COLUMNS = (
    "id, ulid, opportunity_id, event_date, event_type, from_stage, to_stage, summary, created_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardOpportunityRecord:
    return BoardOpportunityRecord.model_validate(dict(row))


def insert_opportunity(
    conn: sqlite3.Connection,
    *,
    organisation: str,
    board_type: Any = None,
    role: Any = None,
    source_firm_id: int | None = None,
    source_text: str | None = None,
    chair_contact_id: int | None = None,
    date_surfaced: date | None = None,
    stage: Any = "surfaced",
    interest: Any = "exploratory",
    next_step: str | None = None,
    notes: str | None = None,
    ulid: str | None = None,
) -> BoardOpportunityRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_opportunity (ulid, organisation, board_type, role, "
        "source_firm_id, source_text, chair_contact_id, date_surfaced, stage, "
        "interest, next_step, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, organisation, _val(board_type), _val(role), source_firm_id,
            source_text, chair_contact_id, date_surfaced, _val(stage) or "surfaced",
            _val(interest) or "exploratory", next_step, notes,
        ),
    )
    return get_opportunity_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_opportunity_by_id(conn: sqlite3.Connection, opportunity_id: int) -> BoardOpportunityRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_opportunity WHERE id = ?", (opportunity_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def get_opportunity_by_ulid(conn: sqlite3.Connection, ulid: str) -> BoardOpportunityRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_opportunity WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_opportunities(
    conn: sqlite3.Connection,
    *,
    stage: Any = None,
    interest: Any = None,
    conflict_cleared: Any = None,
    include_deleted: bool = False,
    sort: str | None = None,
) -> list[BoardOpportunityRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if stage is not None:
        clauses.append("stage = ?")
        params.append(_val(stage))
    if interest is not None:
        clauses.append("interest = ?")
        params.append(_val(interest))
    if conflict_cleared is not None:
        clauses.append("conflict_cleared = ?")
        params.append(_val(conflict_cleared))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    if sort == "date_surfaced":
        order = "date_surfaced IS NULL, date_surfaced DESC, created_at DESC"
    elif sort == "eval":
        order = "eval_weighted_total IS NULL, eval_weighted_total DESC, created_at DESC"
    else:
        order = "created_at DESC"
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_opportunity {where} ORDER BY {order}", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_OPPORTUNITY_FIELDS = {
    "organisation", "board_type", "role", "source_firm_id", "source_text",
    "chair_contact_id", "date_surfaced", "interest", "next_step", "notes",
}


def update_opportunity_fields(
    conn: sqlite3.Connection, opportunity_id: int, fields: dict[str, Any]
) -> BoardOpportunityRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_OPPORTUNITY_FIELDS}
    if not updates:
        return get_opportunity_by_id(conn, opportunity_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE board_opportunity SET {assignments} WHERE id = ?",
        (*updates.values(), opportunity_id),
    )
    return get_opportunity_by_id(conn, opportunity_id)


def set_stage(conn: sqlite3.Connection, opportunity_id: int, stage: Any) -> None:
    conn.execute("UPDATE board_opportunity SET stage = ? WHERE id = ?", (_val(stage), opportunity_id))


def set_conflict_cleared(conn: sqlite3.Connection, opportunity_id: int, conflict_cleared: Any) -> None:
    conn.execute(
        "UPDATE board_opportunity SET conflict_cleared = ? WHERE id = ?",
        (_val(conflict_cleared), opportunity_id),
    )


def set_evaluation(
    conn: sqlite3.Connection, opportunity_id: int, weighted_total: float | None, verdict: Any
) -> None:
    conn.execute(
        "UPDATE board_opportunity SET eval_weighted_total = ?, eval_verdict = ? WHERE id = ?",
        (weighted_total, _val(verdict), opportunity_id),
    )


def soft_delete_opportunity(conn: sqlite3.Connection, opportunity_id: int) -> None:
    conn.execute(
        "UPDATE board_opportunity SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (opportunity_id,),
    )


def restore_opportunity(conn: sqlite3.Connection, opportunity_id: int) -> None:
    conn.execute("UPDATE board_opportunity SET deleted_at = NULL WHERE id = ?", (opportunity_id,))


# ---------- board_opportunity_log (append-only) ----------

def _log_row_to_record(row: sqlite3.Row) -> BoardOpportunityLogRecord:
    return BoardOpportunityLogRecord.model_validate(dict(row))


def insert_log(
    conn: sqlite3.Connection,
    *,
    opportunity_id: int,
    event_date: date,
    event_type: Any,
    from_stage: str | None = None,
    to_stage: str | None = None,
    summary: str | None = None,
    ulid: str | None = None,
) -> BoardOpportunityLogRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_opportunity_log (ulid, opportunity_id, event_date, event_type, "
        "from_stage, to_stage, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, opportunity_id, event_date, _val(event_type), from_stage, to_stage, summary),
    )
    row = conn.execute(
        f"SELECT {_LOG_COLUMNS} FROM board_opportunity_log WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _log_row_to_record(row)


def list_log(conn: sqlite3.Connection, opportunity_id: int) -> list[BoardOpportunityLogRecord]:
    rows = conn.execute(
        f"SELECT {_LOG_COLUMNS} FROM board_opportunity_log WHERE opportunity_id = ? "
        "ORDER BY event_date DESC, id DESC",
        (opportunity_id,),
    ).fetchall()
    return [_log_row_to_record(r) for r in rows]
