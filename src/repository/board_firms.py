"""board_firm repository — pure data access."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models import BoardFirmRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, name, firm_type, geography, sectors_level, ai_on_boards_hook, "
    "tier, status, next_action, notes, source_url, created_at, updated_at, deleted_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _encode_geography(v: Any) -> str | None:
    """Store the multi-value geography as a JSON array of plain strings."""
    if v is None:
        return None
    return json.dumps([_val(x) for x in v])


def _row_to_record(row: sqlite3.Row) -> BoardFirmRecord:
    return BoardFirmRecord.model_validate(dict(row))


def insert_firm(
    conn: sqlite3.Connection,
    *,
    name: str,
    firm_type: Any = None,
    geography: Any = None,
    sectors_level: str | None = None,
    ai_on_boards_hook: str | None = None,
    tier: int | None = None,
    status: Any = "to_approach",
    next_action: str | None = None,
    notes: str | None = None,
    source_url: str | None = None,
    ulid: str | None = None,
) -> BoardFirmRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_firm (ulid, name, firm_type, geography, sectors_level, "
        "ai_on_boards_hook, tier, status, next_action, notes, source_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, name, _val(firm_type), _encode_geography(geography),
            sectors_level, ai_on_boards_hook, tier, _val(status) or "to_approach",
            next_action, notes, source_url,
        ),
    )
    return get_firm_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_firm_by_id(conn: sqlite3.Connection, firm_id: int) -> BoardFirmRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_firm WHERE id = ?", (firm_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_firms_by_ids(conn: sqlite3.Connection, ids: list[int]) -> dict[int, BoardFirmRecord]:
    unique = list({i for i in ids if i is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_firm WHERE id IN ({placeholders})", unique
    ).fetchall()
    return {r["id"]: _row_to_record(r) for r in rows}


def get_firm_by_ulid(conn: sqlite3.Connection, ulid: str) -> BoardFirmRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_firm WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_firm_by_name(conn: sqlite3.Connection, name: str) -> BoardFirmRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM board_firm WHERE name = ? AND deleted_at IS NULL",
        (name,),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_firms(
    conn: sqlite3.Connection,
    *,
    status: Any = None,
    tier: int | None = None,
    include_deleted: bool = False,
) -> list[BoardFirmRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if status is not None:
        clauses.append("status = ?")
        params.append(_val(status))
    if tier is not None:
        clauses.append("tier = ?")
        params.append(tier)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_firm {where} "
        "ORDER BY tier IS NULL, tier ASC, name ASC",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_FIRM_FIELDS = {
    "name", "firm_type", "geography", "sectors_level", "ai_on_boards_hook",
    "tier", "status", "next_action", "notes", "source_url",
}


def update_firm_fields(
    conn: sqlite3.Connection, firm_id: int, fields: dict[str, Any]
) -> BoardFirmRecord | None:
    updates: dict[str, Any] = {}
    for k, v in fields.items():
        if k not in _ALLOWED_FIRM_FIELDS:
            continue
        updates[k] = _encode_geography(v) if k == "geography" else _val(v)
    if not updates:
        return get_firm_by_id(conn, firm_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE board_firm SET {assignments} WHERE id = ?",
        (*updates.values(), firm_id),
    )
    return get_firm_by_id(conn, firm_id)


def soft_delete_firm(conn: sqlite3.Connection, firm_id: int) -> None:
    conn.execute(
        "UPDATE board_firm SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (firm_id,),
    )


def restore_firm(conn: sqlite3.Connection, firm_id: int) -> None:
    conn.execute("UPDATE board_firm SET deleted_at = NULL WHERE id = ?", (firm_id,))
