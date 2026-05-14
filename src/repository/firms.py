"""Firms repository — pure data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import FirmRecord, FirmTier, RelationshipState
from ..ulid_helpers import new_ulid


_COLUMNS = (
    "id, ulid, name, tier, region, relationship_state, primary_focus, "
    "notes_summary, created_at, updated_at, deleted_at"
)


def _row_to_record(row: sqlite3.Row) -> FirmRecord:
    return FirmRecord.model_validate(dict(row))


def insert_firm(
    conn: sqlite3.Connection,
    *,
    name: str,
    tier: FirmTier | str,
    region: str | None = None,
    relationship_state: RelationshipState | str = RelationshipState.cold,
    primary_focus: str | None = None,
    notes_summary: str | None = None,
    ulid: str | None = None,
) -> FirmRecord:
    ulid_value = ulid or new_ulid()
    tier_value = tier.value if isinstance(tier, FirmTier) else FirmTier(tier).value
    state_value = (
        relationship_state.value if isinstance(relationship_state, RelationshipState)
        else RelationshipState(relationship_state).value
    )
    cur = conn.execute(
        "INSERT INTO firms (ulid, name, tier, region, relationship_state, primary_focus, notes_summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, name, tier_value, region, state_value, primary_focus, notes_summary),
    )
    return get_firm_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_firm_by_id(conn: sqlite3.Connection, firm_id: int) -> FirmRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM firms WHERE id = ?", (firm_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_firm_by_ulid(conn: sqlite3.Connection, ulid: str) -> FirmRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM firms WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_firm_by_name(conn: sqlite3.Connection, name: str) -> FirmRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM firms WHERE name = ?", (name,)).fetchone()
    return _row_to_record(row) if row else None


def list_firms(
    conn: sqlite3.Connection,
    *,
    tier: FirmTier | None = None,
    relationship_state: RelationshipState | None = None,
    include_deleted: bool = False,
) -> list[FirmRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if tier is not None:
        clauses.append("tier = ?")
        params.append(tier.value)
    if relationship_state is not None:
        clauses.append("relationship_state = ?")
        params.append(relationship_state.value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM firms {where} ORDER BY name", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_FIRM_FIELDS = {
    "name", "tier", "region", "relationship_state", "primary_focus", "notes_summary",
}


def update_firm_fields(conn: sqlite3.Connection, firm_id: int, fields: dict[str, Any]) -> FirmRecord | None:
    updates = {k: (v.value if hasattr(v, "value") else v) for k, v in fields.items() if k in _ALLOWED_FIRM_FIELDS}
    if not updates:
        return get_firm_by_id(conn, firm_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE firms SET {assignments} WHERE id = ?",
        (*updates.values(), firm_id),
    )
    return get_firm_by_id(conn, firm_id)


def soft_delete_firm(conn: sqlite3.Connection, firm_id: int) -> None:
    conn.execute("UPDATE firms SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL", (firm_id,))


def restore_firm(conn: sqlite3.Connection, firm_id: int) -> None:
    conn.execute("UPDATE firms SET deleted_at = NULL WHERE id = ?", (firm_id,))
