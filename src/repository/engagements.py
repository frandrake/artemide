"""Engagements + engagement_log repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import EngagementLogRecord, EngagementRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, org_id, role_title, role_type, source, source_partner_id, "
    "stage, interest, comp_base_gbp, comp_total_gbp, comp_equity_note, "
    "fit_score, fit_breakdown, next_step, next_step_date, closed_reason, "
    "created_at, updated_at, deleted_at"
)

_LOG_COLUMNS = (
    "id, ulid, engagement_id, event_date, event_type, from_stage, to_stage, summary, created_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> EngagementRecord:
    return EngagementRecord.model_validate(dict(row))


def insert_engagement(
    conn: sqlite3.Connection,
    *,
    org_id: int,
    role_title: str,
    role_type: Any = None,
    source: Any = None,
    source_partner_id: int | None = None,
    stage: Any = "surfaced",
    interest: Any = "exploratory",
    comp_base_gbp: int | None = None,
    comp_total_gbp: int | None = None,
    comp_equity_note: str | None = None,
    next_step: str | None = None,
    next_step_date: date | None = None,
    ulid: str | None = None,
) -> EngagementRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO engagements (ulid, org_id, role_title, role_type, source, "
        "source_partner_id, stage, interest, comp_base_gbp, comp_total_gbp, "
        "comp_equity_note, next_step, next_step_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, org_id, role_title, _val(role_type), _val(source),
            source_partner_id, _val(stage) or "surfaced", _val(interest) or "exploratory",
            comp_base_gbp, comp_total_gbp, comp_equity_note, next_step, next_step_date,
        ),
    )
    return get_engagement_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_engagement_by_id(conn: sqlite3.Connection, engagement_id: int) -> EngagementRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_engagements_by_ids(conn: sqlite3.Connection, ids: list[int]) -> dict[int, EngagementRecord]:
    """Batch-load engagements by id (avoids per-row N+1 in list responses)."""
    unique = list({i for i in ids if i is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM engagements WHERE id IN ({placeholders})", unique
    ).fetchall()
    return {r["id"]: _row_to_record(r) for r in rows}


def get_engagement_by_ulid(conn: sqlite3.Connection, ulid: str) -> EngagementRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM engagements WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_engagement_by_org_and_title(
    conn: sqlite3.Connection, org_id: int, role_title: str
) -> EngagementRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM engagements "
        "WHERE org_id = ? AND role_title = ? AND deleted_at IS NULL",
        (org_id, role_title),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_engagements(
    conn: sqlite3.Connection,
    *,
    stage: Any = None,
    interest: Any = None,
    org_id: int | None = None,
    source_partner_id: int | None = None,
    include_deleted: bool = False,
    sort: str | None = None,
) -> list[EngagementRecord]:
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
    if org_id is not None:
        clauses.append("org_id = ?")
        params.append(org_id)
    if source_partner_id is not None:
        clauses.append("source_partner_id = ?")
        params.append(source_partner_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "fit_score IS NULL, fit_score DESC, created_at DESC" if sort == "fit" else "created_at DESC"
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM engagements {where} ORDER BY {order}", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def count_open_by_org(conn: sqlite3.Connection, org_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM engagements "
        "WHERE org_id = ? AND deleted_at IS NULL AND stage != 'closed'",
        (org_id,),
    ).fetchone()
    return int(row[0])


def count_at_stages(conn: sqlite3.Connection, stages: tuple[str, ...]) -> int:
    placeholders = ", ".join("?" for _ in stages)
    row = conn.execute(
        f"SELECT COUNT(*) FROM engagements "
        f"WHERE deleted_at IS NULL AND stage IN ({placeholders})",
        stages,
    ).fetchone()
    return int(row[0])


_ALLOWED_ENGAGEMENT_FIELDS = {
    "role_title", "role_type", "source", "interest",
    "comp_base_gbp", "comp_total_gbp", "comp_equity_note",
    "next_step", "next_step_date",
}


def update_engagement_fields(conn: sqlite3.Connection, engagement_id: int, fields: dict[str, Any]) -> EngagementRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_ENGAGEMENT_FIELDS}
    if not updates:
        return get_engagement_by_id(conn, engagement_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE engagements SET {assignments} WHERE id = ?",
        (*updates.values(), engagement_id),
    )
    return get_engagement_by_id(conn, engagement_id)


def set_stage(conn: sqlite3.Connection, engagement_id: int, stage: Any) -> None:
    conn.execute("UPDATE engagements SET stage = ? WHERE id = ?", (_val(stage), engagement_id))


def set_interest(conn: sqlite3.Connection, engagement_id: int, interest: Any) -> None:
    conn.execute("UPDATE engagements SET interest = ? WHERE id = ?", (_val(interest), engagement_id))


def set_closed(conn: sqlite3.Connection, engagement_id: int, closed_reason: Any) -> None:
    conn.execute(
        "UPDATE engagements SET stage = 'closed', closed_reason = ? WHERE id = ?",
        (_val(closed_reason), engagement_id),
    )


def set_fit(conn: sqlite3.Connection, engagement_id: int, score: int | None, breakdown_json: str | None) -> None:
    conn.execute(
        "UPDATE engagements SET fit_score = ?, fit_breakdown = ? WHERE id = ?",
        (score, breakdown_json, engagement_id),
    )


def soft_delete_engagement(conn: sqlite3.Connection, engagement_id: int) -> None:
    conn.execute(
        "UPDATE engagements SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (engagement_id,),
    )


def restore_engagement(conn: sqlite3.Connection, engagement_id: int) -> None:
    conn.execute("UPDATE engagements SET deleted_at = NULL WHERE id = ?", (engagement_id,))


# ---------- engagement_log ----------

def _log_row_to_record(row: sqlite3.Row) -> EngagementLogRecord:
    return EngagementLogRecord.model_validate(dict(row))


def insert_log(
    conn: sqlite3.Connection,
    *,
    engagement_id: int,
    event_date: date,
    event_type: Any,
    from_stage: str | None = None,
    to_stage: str | None = None,
    summary: str | None = None,
    ulid: str | None = None,
) -> EngagementLogRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO engagement_log (ulid, engagement_id, event_date, event_type, "
        "from_stage, to_stage, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, engagement_id, event_date, _val(event_type), from_stage, to_stage, summary),
    )
    row = conn.execute(
        f"SELECT {_LOG_COLUMNS} FROM engagement_log WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _log_row_to_record(row)


def list_log(conn: sqlite3.Connection, engagement_id: int) -> list[EngagementLogRecord]:
    rows = conn.execute(
        f"SELECT {_LOG_COLUMNS} FROM engagement_log WHERE engagement_id = ? "
        "ORDER BY event_date DESC, id DESC",
        (engagement_id,),
    ).fetchall()
    return [_log_row_to_record(r) for r in rows]
