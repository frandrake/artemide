"""board_contact repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import BoardContactRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, name, role_title, firm_id, practice, email, linkedin, "
    "mutual_connections, relationship, last_contact_date, source_url, notes, "
    "created_at, updated_at, deleted_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardContactRecord:
    return BoardContactRecord.model_validate(dict(row))


def insert_contact(
    conn: sqlite3.Connection,
    *,
    name: str,
    role_title: str | None = None,
    firm_id: int | None = None,
    practice: Any = None,
    email: str | None = None,
    linkedin: str | None = None,
    mutual_connections: str | None = None,
    relationship: Any = "cold",
    last_contact_date: date | None = None,
    source_url: str | None = None,
    notes: str | None = None,
    ulid: str | None = None,
) -> BoardContactRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_contact (ulid, name, role_title, firm_id, practice, email, "
        "linkedin, mutual_connections, relationship, last_contact_date, source_url, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, name, role_title, firm_id, _val(practice), email, linkedin,
            mutual_connections, _val(relationship) or "cold", last_contact_date,
            source_url, notes,
        ),
    )
    return get_contact_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_contact_by_id(conn: sqlite3.Connection, contact_id: int) -> BoardContactRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_contact WHERE id = ?", (contact_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_contacts_by_ids(conn: sqlite3.Connection, ids: list[int]) -> dict[int, BoardContactRecord]:
    unique = list({i for i in ids if i is not None})
    if not unique:
        return {}
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_contact WHERE id IN ({placeholders})", unique
    ).fetchall()
    return {r["id"]: _row_to_record(r) for r in rows}


def get_contact_by_ulid(conn: sqlite3.Connection, ulid: str) -> BoardContactRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_contact WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_contact_by_name(
    conn: sqlite3.Connection, firm_id: int | None, name: str
) -> BoardContactRecord | None:
    if firm_id is None:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM board_contact "
            "WHERE firm_id IS NULL AND name = ? AND deleted_at IS NULL",
            (name,),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM board_contact "
            "WHERE firm_id = ? AND name = ? AND deleted_at IS NULL",
            (firm_id, name),
        ).fetchone()
    return _row_to_record(row) if row else None


def list_contacts(
    conn: sqlite3.Connection,
    *,
    firm_id: int | None = None,
    relationship: Any = None,
    include_deleted: bool = False,
) -> list[BoardContactRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if firm_id is not None:
        clauses.append("firm_id = ?")
        params.append(firm_id)
    if relationship is not None:
        clauses.append("relationship = ?")
        params.append(_val(relationship))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_contact {where} ORDER BY name ASC", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_CONTACT_FIELDS = {
    "name", "role_title", "firm_id", "practice", "email", "linkedin",
    "mutual_connections", "relationship", "last_contact_date", "source_url", "notes",
}


def update_contact_fields(
    conn: sqlite3.Connection, contact_id: int, fields: dict[str, Any]
) -> BoardContactRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_CONTACT_FIELDS}
    if not updates:
        return get_contact_by_id(conn, contact_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE board_contact SET {assignments} WHERE id = ?",
        (*updates.values(), contact_id),
    )
    return get_contact_by_id(conn, contact_id)


def soft_delete_contact(conn: sqlite3.Connection, contact_id: int) -> None:
    conn.execute(
        "UPDATE board_contact SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (contact_id,),
    )


def restore_contact(conn: sqlite3.Connection, contact_id: int) -> None:
    conn.execute("UPDATE board_contact SET deleted_at = NULL WHERE id = ?", (contact_id,))
