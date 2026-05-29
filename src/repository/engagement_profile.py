"""Engagement profile repository — versioned fit criteria."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models import EngagementProfileRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, version, active, comp_base_floor_gbp, comp_total_target_gbp, "
    "accepted_role_types, accepted_scale_bands, hard_exclusions, weights, created_at"
)


def _row_to_record(row: sqlite3.Row) -> EngagementProfileRecord:
    return EngagementProfileRecord.model_validate(dict(row))


def insert_profile(
    conn: sqlite3.Connection,
    *,
    version: int,
    active: bool,
    comp_base_floor_gbp: int,
    comp_total_target_gbp: int,
    accepted_role_types: list[str],
    accepted_scale_bands: list[str],
    hard_exclusions: list[str],
    weights: dict[str, int],
    ulid: str | None = None,
) -> EngagementProfileRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO engagement_profile (ulid, version, active, comp_base_floor_gbp, "
        "comp_total_target_gbp, accepted_role_types, accepted_scale_bands, "
        "hard_exclusions, weights) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, version, 1 if active else 0, comp_base_floor_gbp,
            comp_total_target_gbp, json.dumps(accepted_role_types),
            json.dumps(accepted_scale_bands), json.dumps(hard_exclusions),
            json.dumps(weights),
        ),
    )
    return get_profile_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_profile_by_id(conn: sqlite3.Connection, profile_id: int) -> EngagementProfileRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM engagement_profile WHERE id = ?", (profile_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_profile_by_ulid(conn: sqlite3.Connection, ulid: str) -> EngagementProfileRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM engagement_profile WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_active_profile(conn: sqlite3.Connection) -> EngagementProfileRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM engagement_profile WHERE active = 1").fetchone()
    return _row_to_record(row) if row else None


def list_profiles(conn: sqlite3.Connection) -> list[EngagementProfileRecord]:
    rows = conn.execute(f"SELECT {_COLUMNS} FROM engagement_profile ORDER BY version DESC").fetchall()
    return [_row_to_record(r) for r in rows]


def max_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM engagement_profile").fetchone()
    return int(row[0])


def deactivate_all(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE engagement_profile SET active = 0 WHERE active = 1")
