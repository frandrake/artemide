"""Templates repository — pure data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import TemplateRecord
from ..ulid_helpers import new_ulid


_COLUMNS = (
    "id, ulid, name, category, channel, subject_template, body_template, "
    "description, created_at, updated_at, deleted_at"
)


def _row_to_record(row: sqlite3.Row) -> TemplateRecord:
    return TemplateRecord.model_validate(dict(row))


def insert_template(
    conn: sqlite3.Connection,
    *,
    name: str,
    channel: str,
    body_template: str,
    subject_template: str | None = None,
    category: str | None = None,
    description: str | None = None,
    ulid: str | None = None,
) -> TemplateRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO template "
        "(ulid, name, category, channel, subject_template, body_template, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, name, category, channel, subject_template, body_template, description),
    )
    return get_template_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_template_by_id(conn: sqlite3.Connection, template_id: int) -> TemplateRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM template WHERE id = ?", (template_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_template_by_ulid(conn: sqlite3.Connection, ulid: str) -> TemplateRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM template WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_template_by_name(conn: sqlite3.Connection, name: str) -> TemplateRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM template WHERE name = ?", (name,)).fetchone()
    return _row_to_record(row) if row else None


def list_templates(
    conn: sqlite3.Connection,
    *,
    channel: str | None = None,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[TemplateRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if channel is not None:
        clauses.append("channel = ?")
        params.append(channel)
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM template {where} ORDER BY name", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_TEMPLATE_FIELDS = {
    "name", "category", "channel", "subject_template", "body_template", "description",
}


def update_template_fields(
    conn: sqlite3.Connection, template_id: int, fields: dict[str, Any]
) -> TemplateRecord | None:
    updates = {
        k: (v.value if hasattr(v, "value") else v)
        for k, v in fields.items() if k in _ALLOWED_TEMPLATE_FIELDS
    }
    if not updates:
        return get_template_by_id(conn, template_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE template SET {assignments} WHERE id = ?",
        (*updates.values(), template_id),
    )
    return get_template_by_id(conn, template_id)


def soft_delete_template(conn: sqlite3.Connection, template_id: int) -> None:
    conn.execute(
        "UPDATE template SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (template_id,),
    )


def restore_template(conn: sqlite3.Connection, template_id: int) -> None:
    conn.execute("UPDATE template SET deleted_at = NULL WHERE id = ?", (template_id,))
