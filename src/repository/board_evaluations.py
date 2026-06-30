"""board_evaluation repository (1:1 with opportunity) — pure data access."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models import BoardEvaluationRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, opportunity_id, score_chair_board_quality, score_mandate_contribution_fit, "
    "score_governance_health_risk, score_time_conflict_cost, score_brand_portfolio_value, "
    "score_terms, weighted_total, hard_disqualifiers, firo_b_fit_notes, verdict, "
    "created_at, updated_at"
)

_SCORE_FIELDS = (
    "score_chair_board_quality", "score_mandate_contribution_fit",
    "score_governance_health_risk", "score_time_conflict_cost",
    "score_brand_portfolio_value", "score_terms",
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardEvaluationRecord:
    return BoardEvaluationRecord.model_validate(dict(row))


def get_by_opportunity(conn: sqlite3.Connection, opportunity_id: int) -> BoardEvaluationRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_evaluation WHERE opportunity_id = ?",
        (opportunity_id,),
    ).fetchone()
    return _row_to_record(row) if row else None


def get_by_opportunity_ids(
    conn: sqlite3.Connection, ids: list[int]
) -> dict[int, BoardEvaluationRecord]:
    unique = list({i for i in ids if i is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_evaluation WHERE opportunity_id IN ({placeholders})",
        unique,
    ).fetchall()
    return {r["opportunity_id"]: _row_to_record(r) for r in rows}


def upsert_by_opportunity(
    conn: sqlite3.Connection,
    *,
    opportunity_id: int,
    scores: dict[str, int],
    weighted_total: float,
    hard_disqualifiers: list[str],
    firo_b_fit_notes: str | None,
    verdict: Any,
    ulid: str | None = None,
) -> BoardEvaluationRecord:
    disq_json = json.dumps(list(hard_disqualifiers))
    score_values = [scores.get(f) for f in _SCORE_FIELDS]
    existing = get_by_opportunity(conn, opportunity_id)
    if existing is None:
        ulid_value = ulid or new_ulid()
        cols = ", ".join(_SCORE_FIELDS)
        placeholders = ", ".join("?" * len(_SCORE_FIELDS))
        conn.execute(
            f"INSERT INTO board_evaluation (ulid, opportunity_id, {cols}, weighted_total, "
            "hard_disqualifiers, firo_b_fit_notes, verdict) "
            f"VALUES (?, ?, {placeholders}, ?, ?, ?, ?)",
            (ulid_value, opportunity_id, *score_values, weighted_total, disq_json,
             firo_b_fit_notes, _val(verdict)),
        )
    else:
        assignments = ", ".join(f"{f} = ?" for f in _SCORE_FIELDS)
        conn.execute(
            f"UPDATE board_evaluation SET {assignments}, weighted_total = ?, "
            "hard_disqualifiers = ?, firo_b_fit_notes = ?, verdict = ? "
            "WHERE opportunity_id = ?",
            (*score_values, weighted_total, disq_json, firo_b_fit_notes, _val(verdict),
             opportunity_id),
        )
    return get_by_opportunity(conn, opportunity_id)  # type: ignore[return-value]
