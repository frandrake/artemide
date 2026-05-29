"""API tokens repository — owner/bot multi-actor model (Rule 18).

Only the SHA-256 hash of a bearer token is ever stored.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import ApiTokenRecord
from ..ulid_helpers import new_ulid

_COLUMNS = "id, ulid, token_hash, actor, role, active, created_at, rotated_at"


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> ApiTokenRecord:
    return ApiTokenRecord.model_validate(dict(row))


def insert_token(
    conn: sqlite3.Connection,
    *,
    token_hash: str,
    actor: str,
    role: Any,
    active: bool = True,
    ulid: str | None = None,
) -> ApiTokenRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO api_tokens (ulid, token_hash, actor, role, active) "
        "VALUES (?, ?, ?, ?, ?)",
        (ulid_value, token_hash, actor, _val(role), 1 if active else 0),
    )
    row = conn.execute(f"SELECT {_COLUMNS} FROM api_tokens WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_record(row)


def get_active_by_hash(conn: sqlite3.Connection, token_hash: str) -> ApiTokenRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM api_tokens WHERE token_hash = ? AND active = 1",
        (token_hash,),
    ).fetchone()
    return _row_to_record(row) if row else None


def get_by_hash(conn: sqlite3.Connection, token_hash: str) -> ApiTokenRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM api_tokens WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_by_role(conn: sqlite3.Connection, role: Any) -> list[ApiTokenRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM api_tokens WHERE role = ? ORDER BY created_at DESC",
        (_val(role),),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def deactivate_by_role(conn: sqlite3.Connection, role: Any) -> None:
    conn.execute(
        "UPDATE api_tokens SET active = 0, rotated_at = CURRENT_TIMESTAMP "
        "WHERE role = ? AND active = 1",
        (_val(role),),
    )


def deactivate(conn: sqlite3.Connection, token_id: int) -> None:
    conn.execute(
        "UPDATE api_tokens SET active = 0, rotated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (token_id,),
    )
