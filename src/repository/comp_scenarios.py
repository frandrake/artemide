"""Compensation scenarios repository — pure data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import CompScenarioRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, name, status, is_baseline, engagement_id, "
    "base_gbp, cash_bonus_gbp, equity_gbp, equity_note, pension_pct, "
    "healthcare_gbp, car_allowance_gbp, other_gbp, benefits_note, "
    "created_at, updated_at, deleted_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> CompScenarioRecord:
    return CompScenarioRecord.model_validate(dict(row))


def insert_scenario(
    conn: sqlite3.Connection,
    *,
    name: str,
    status: Any = "offer",
    is_baseline: bool = False,
    engagement_id: int | None = None,
    base_gbp: int | None = None,
    cash_bonus_gbp: int | None = None,
    equity_gbp: int | None = None,
    equity_note: str | None = None,
    pension_pct: float | None = None,
    healthcare_gbp: int | None = None,
    car_allowance_gbp: int | None = None,
    other_gbp: int | None = None,
    benefits_note: str | None = None,
    ulid: str | None = None,
) -> CompScenarioRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO compensation_scenarios (ulid, name, status, is_baseline, "
        "engagement_id, base_gbp, cash_bonus_gbp, equity_gbp, equity_note, "
        "pension_pct, healthcare_gbp, car_allowance_gbp, other_gbp, benefits_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, name, _val(status) or "offer", 1 if is_baseline else 0,
            engagement_id, base_gbp, cash_bonus_gbp, equity_gbp, equity_note,
            pension_pct, healthcare_gbp, car_allowance_gbp, other_gbp, benefits_note,
        ),
    )
    return get_scenario_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_scenario_by_id(conn: sqlite3.Connection, scenario_id: int) -> CompScenarioRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM compensation_scenarios WHERE id = ?", (scenario_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def get_scenario_by_ulid(conn: sqlite3.Connection, ulid: str) -> CompScenarioRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM compensation_scenarios WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _row_to_record(row) if row else None


def get_scenario_by_name(conn: sqlite3.Connection, name: str) -> CompScenarioRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM compensation_scenarios "
        "WHERE name = ? AND deleted_at IS NULL",
        (name,),
    ).fetchone()
    return _row_to_record(row) if row else None


def get_baseline(conn: sqlite3.Connection) -> CompScenarioRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM compensation_scenarios "
        "WHERE is_baseline = 1 AND deleted_at IS NULL"
    ).fetchone()
    return _row_to_record(row) if row else None


def list_scenarios(
    conn: sqlite3.Connection,
    *,
    status: Any = None,
    include_deleted: bool = False,
) -> list[CompScenarioRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if status is not None:
        clauses.append("status = ?")
        params.append(_val(status))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM compensation_scenarios {where} "
        "ORDER BY is_baseline DESC, created_at ASC",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_SCENARIO_FIELDS = {
    "name", "status", "engagement_id",
    "base_gbp", "cash_bonus_gbp", "equity_gbp", "equity_note", "pension_pct",
    "healthcare_gbp", "car_allowance_gbp", "other_gbp", "benefits_note",
}


def update_scenario_fields(
    conn: sqlite3.Connection, scenario_id: int, fields: dict[str, Any]
) -> CompScenarioRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_SCENARIO_FIELDS}
    if not updates:
        return get_scenario_by_id(conn, scenario_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE compensation_scenarios SET {assignments} WHERE id = ?",
        (*updates.values(), scenario_id),
    )
    return get_scenario_by_id(conn, scenario_id)


def set_baseline(conn: sqlite3.Connection, scenario_id: int) -> None:
    """Swap the baseline anchor. Caller wraps in a transaction; clearing first
    keeps the partial unique index satisfied at every step."""
    conn.execute(
        "UPDATE compensation_scenarios SET is_baseline = 0 "
        "WHERE is_baseline = 1 AND deleted_at IS NULL"
    )
    conn.execute(
        "UPDATE compensation_scenarios SET is_baseline = 1 WHERE id = ?",
        (scenario_id,),
    )


def clear_baseline_flag(conn: sqlite3.Connection, scenario_id: int) -> None:
    conn.execute(
        "UPDATE compensation_scenarios SET is_baseline = 0 WHERE id = ?",
        (scenario_id,),
    )


def soft_delete_scenario(conn: sqlite3.Connection, scenario_id: int) -> None:
    conn.execute(
        "UPDATE compensation_scenarios SET deleted_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND deleted_at IS NULL",
        (scenario_id,),
    )


def restore_scenario(conn: sqlite3.Connection, scenario_id: int) -> None:
    conn.execute(
        "UPDATE compensation_scenarios SET deleted_at = NULL WHERE id = ?",
        (scenario_id,),
    )
