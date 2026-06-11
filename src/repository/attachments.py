"""Attachments repository — pure data access.

Read paths are split so the `content` BLOB is never selected incidentally:
`_META_COLUMNS` feeds `AttachmentRecord` (which has no `content` field), and
`get_content` is the only query that SELECTs the bytes.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import AttachmentRecord
from ..ulid_helpers import new_ulid

# Everything except `content` — AttachmentRecord declares no content field.
_META_COLUMNS = (
    "id, ulid, entity_type, entity_id, kind, filename, content_type, "
    "byte_size, sha256, uploaded_by, created_at, deleted_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> AttachmentRecord:
    return AttachmentRecord.model_validate(dict(row))


def insert_attachment(
    conn: sqlite3.Connection,
    *,
    entity_type: Any,
    entity_id: str,
    kind: Any,
    filename: str,
    content_type: str,
    content: bytes,
    sha256: str,
    uploaded_by: str,
    ulid: str | None = None,
) -> AttachmentRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO attachments (ulid, entity_type, entity_id, kind, filename, "
        "content_type, byte_size, sha256, content, uploaded_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, _val(entity_type), entity_id, _val(kind), filename,
            content_type, len(content), sha256, content, uploaded_by,
        ),
    )
    row = conn.execute(
        f"SELECT {_META_COLUMNS} FROM attachments WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _row_to_record(row)


def get_attachment_by_ulid(conn: sqlite3.Connection, ulid: str) -> AttachmentRecord | None:
    row = conn.execute(
        f"SELECT {_META_COLUMNS} FROM attachments WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_by_entity(
    conn: sqlite3.Connection, entity_type: Any, entity_id: str
) -> list[AttachmentRecord]:
    rows = conn.execute(
        f"SELECT {_META_COLUMNS} FROM attachments "
        "WHERE entity_type = ? AND entity_id = ? AND deleted_at IS NULL "
        "ORDER BY created_at DESC, id DESC",
        (_val(entity_type), entity_id),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def find_live_by_entity_sha(
    conn: sqlite3.Connection, entity_type: Any, entity_id: str, sha256: str
) -> AttachmentRecord | None:
    """Idempotency lookup: an identical (live) upload on the same target."""
    row = conn.execute(
        f"SELECT {_META_COLUMNS} FROM attachments "
        "WHERE entity_type = ? AND entity_id = ? AND sha256 = ? AND deleted_at IS NULL",
        (_val(entity_type), entity_id, sha256),
    ).fetchone()
    return _row_to_record(row) if row else None


def get_content(
    conn: sqlite3.Connection, ulid: str
) -> tuple[bytes, str, str] | None:
    """The ONLY query that selects the BLOB. Returns (content, content_type,
    filename) for a live attachment, or None."""
    row = conn.execute(
        "SELECT content, content_type, filename FROM attachments "
        "WHERE ulid = ? AND deleted_at IS NULL",
        (ulid,),
    ).fetchone()
    if row is None:
        return None
    return bytes(row["content"]), row["content_type"], row["filename"]


def soft_delete(conn: sqlite3.Connection, attachment_id: int) -> None:
    conn.execute(
        "UPDATE attachments SET deleted_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND deleted_at IS NULL",
        (attachment_id,),
    )


def restore(conn: sqlite3.Connection, attachment_id: int) -> None:
    conn.execute("UPDATE attachments SET deleted_at = NULL WHERE id = ?", (attachment_id,))
