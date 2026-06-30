"""board_task repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import BoardTaskRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, linked_entity_type, linked_entity_ulid, title, due_date, status, "
    "created_at, updated_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> BoardTaskRecord:
    return BoardTaskRecord.model_validate(dict(row))


def insert_task(
    conn: sqlite3.Connection,
    *,
    title: str,
    linked_entity_type: Any = None,
    linked_entity_ulid: str | None = None,
    due_date: date | None = None,
    status: Any = "open",
    ulid: str | None = None,
) -> BoardTaskRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO board_task (ulid, linked_entity_type, linked_entity_ulid, title, "
        "due_date, status) VALUES (?, ?, ?, ?, ?, ?)",
        (ulid_value, _val(linked_entity_type), linked_entity_ulid, title, due_date,
         _val(status) or "open"),
    )
    return get_task_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_task_by_id(conn: sqlite3.Connection, task_id: int) -> BoardTaskRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_task WHERE id = ?", (task_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_task_by_ulid(conn: sqlite3.Connection, ulid: str) -> BoardTaskRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM board_task WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def list_tasks(
    conn: sqlite3.Connection,
    *,
    status: Any = None,
    due_on_or_before: date | None = None,
) -> list[BoardTaskRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(_val(status))
    if due_on_or_before is not None:
        clauses.append("due_date IS NOT NULL AND due_date <= ?")
        params.append(due_on_or_before)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM board_task {where} "
        "ORDER BY status ASC, due_date IS NULL, due_date ASC, id ASC",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_TASK_FIELDS = {"title", "linked_entity_type", "linked_entity_ulid", "due_date", "status"}


def update_task_fields(
    conn: sqlite3.Connection, task_id: int, fields: dict[str, Any]
) -> BoardTaskRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_TASK_FIELDS}
    if not updates:
        return get_task_by_id(conn, task_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE board_task SET {assignments} WHERE id = ?",
        (*updates.values(), task_id),
    )
    return get_task_by_id(conn, task_id)


def set_status(conn: sqlite3.Connection, task_id: int, status: Any) -> None:
    conn.execute("UPDATE board_task SET status = ? WHERE id = ?", (_val(status), task_id))
