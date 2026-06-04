"""Messages repository — the outbound draft queue."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import MessageRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, kind, partner_id, engagement_id, channel, recipient_hint, "
    "subject, body, rationale, status, source_ref, created_by_transport, "
    "approved_at, sent_at, created_at, updated_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord.model_validate(dict(row))


def insert_message(
    conn: sqlite3.Connection,
    *,
    body: str,
    kind: Any = None,
    partner_id: int | None = None,
    engagement_id: int | None = None,
    channel: Any = None,
    recipient_hint: str | None = None,
    subject: str | None = None,
    rationale: str | None = None,
    source_ref: str | None = None,
    created_by_transport: str | None = None,
    ulid: str | None = None,
) -> MessageRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO messages (ulid, kind, partner_id, engagement_id, channel, "
        "recipient_hint, subject, body, rationale, status, source_ref, created_by_transport) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?)",
        (
            ulid_value, _val(kind), partner_id, engagement_id, _val(channel),
            recipient_hint, subject, body, rationale, source_ref, created_by_transport,
        ),
    )
    return get_message_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_message_by_id(conn: sqlite3.Connection, message_id: int) -> MessageRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_message_by_ulid(conn: sqlite3.Connection, ulid: str) -> MessageRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM messages WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_message_by_source_ref(conn: sqlite3.Connection, source_ref: str) -> MessageRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM messages WHERE source_ref = ?", (source_ref,)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_messages(
    conn: sqlite3.Connection,
    *,
    status: Any = None,
    partner_id: int | None = None,
    engagement_id: int | None = None,
) -> list[MessageRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(_val(status))
    if partner_id is not None:
        clauses.append("partner_id = ?")
        params.append(partner_id)
    if engagement_id is not None:
        clauses.append("engagement_id = ?")
        params.append(engagement_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM messages {where} ORDER BY created_at DESC", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def set_status(conn: sqlite3.Connection, message_id: int, status: Any) -> None:
    conn.execute("UPDATE messages SET status = ? WHERE id = ?", (_val(status), message_id))


def mark_approved(conn: sqlite3.Connection, message_id: int) -> None:
    conn.execute(
        "UPDATE messages SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (message_id,),
    )


def mark_sent(conn: sqlite3.Connection, message_id: int) -> None:
    conn.execute(
        "UPDATE messages SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
        (message_id,),
    )


def update_body_subject(
    conn: sqlite3.Connection, message_id: int, *, subject: str | None, body: str | None
) -> None:
    # Editing reverts the message to an unapproved ('edited') state, so any prior
    # approval no longer applies — clear approved_at to keep the trail honest.
    sets: list[str] = ["status = 'edited'", "approved_at = NULL"]
    params: list[Any] = []
    if subject is not None:
        sets.append("subject = ?")
        params.append(subject)
    if body is not None:
        sets.append("body = ?")
        params.append(body)
    params.append(message_id)
    conn.execute(f"UPDATE messages SET {', '.join(sets)} WHERE id = ?", params)


def count_by_status(conn: sqlite3.Connection, status: Any) -> int:
    row = conn.execute("SELECT COUNT(*) FROM messages WHERE status = ?", (_val(status),)).fetchone()
    return int(row[0])
