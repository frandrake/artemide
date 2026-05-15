"""Outreach repository — drafts, versions, messages.

A closed family. Drafts hold head state; outreach_draft_version is the
edit history; outreach_message is the immutable send log.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any

from ..models import (
    OutreachDraftRecord,
    OutreachDraftVersionRecord,
    OutreachMessageRecord,
)
from ..ulid_helpers import new_ulid


# ---------- drafts ----------

_DRAFT_COLUMNS = (
    "id, ulid, partner_id, template_id, channel, subject, body, status, version, "
    "sent_message_id, created_at, updated_at, archived_at"
)


def _draft_row(row: sqlite3.Row) -> OutreachDraftRecord:
    return OutreachDraftRecord.model_validate(dict(row))


def insert_draft(
    conn: sqlite3.Connection,
    *,
    partner_id: int,
    channel: str,
    body: str,
    subject: str | None = None,
    template_id: int | None = None,
    status: str = "draft",
    ulid: str | None = None,
) -> OutreachDraftRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO outreach_draft "
        "(ulid, partner_id, template_id, channel, subject, body, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ulid_value, partner_id, template_id, channel, subject, body, status),
    )
    return get_draft_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_draft_by_id(conn: sqlite3.Connection, draft_id: int) -> OutreachDraftRecord | None:
    row = conn.execute(
        f"SELECT {_DRAFT_COLUMNS} FROM outreach_draft WHERE id = ?", (draft_id,)
    ).fetchone()
    return _draft_row(row) if row else None


def get_draft_by_ulid(conn: sqlite3.Connection, ulid: str) -> OutreachDraftRecord | None:
    row = conn.execute(
        f"SELECT {_DRAFT_COLUMNS} FROM outreach_draft WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _draft_row(row) if row else None


def list_drafts_by_partner(
    conn: sqlite3.Connection, partner_id: int, *, include_archived: bool = False
) -> list[OutreachDraftRecord]:
    clauses = ["partner_id = ?"]
    params: list[Any] = [partner_id]
    if not include_archived:
        clauses.append("status != 'archived'")
    rows = conn.execute(
        f"SELECT {_DRAFT_COLUMNS} FROM outreach_draft WHERE {' AND '.join(clauses)} "
        f"ORDER BY updated_at DESC",
        params,
    ).fetchall()
    return [_draft_row(r) for r in rows]


def list_drafts(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    channel: str | None = None,
    partner_id: int | None = None,
    limit: int = 50,
) -> list[OutreachDraftRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if channel is not None:
        clauses.append("channel = ?")
        params.append(channel)
    if partner_id is not None:
        clauses.append("partner_id = ?")
        params.append(partner_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))
    rows = conn.execute(
        f"SELECT {_DRAFT_COLUMNS} FROM outreach_draft {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_draft_row(r) for r in rows]


_ALLOWED_DRAFT_FIELDS = {
    "subject", "body", "channel", "status", "template_id", "version", "sent_message_id",
}


def update_draft_fields(
    conn: sqlite3.Connection, draft_id: int, fields: dict[str, Any]
) -> OutreachDraftRecord | None:
    updates = {
        k: (v.value if hasattr(v, "value") else v)
        for k, v in fields.items() if k in _ALLOWED_DRAFT_FIELDS
    }
    if not updates:
        return get_draft_by_id(conn, draft_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE outreach_draft SET {assignments} WHERE id = ?",
        (*updates.values(), draft_id),
    )
    return get_draft_by_id(conn, draft_id)


def archive_draft(conn: sqlite3.Connection, draft_id: int) -> None:
    conn.execute(
        "UPDATE outreach_draft SET status = 'archived', archived_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (draft_id,),
    )


def attach_message_to_draft(
    conn: sqlite3.Connection, draft_id: int, message_id: int
) -> None:
    conn.execute(
        "UPDATE outreach_draft SET status = 'sent', sent_message_id = ? WHERE id = ?",
        (message_id, draft_id),
    )


# ---------- versions ----------

_VERSION_COLUMNS = (
    "id, ulid, draft_id, version, subject, body, author_actor, created_at"
)


def _version_row(row: sqlite3.Row) -> OutreachDraftVersionRecord:
    return OutreachDraftVersionRecord.model_validate(dict(row))


def insert_draft_version(
    conn: sqlite3.Connection,
    *,
    draft_id: int,
    version: int,
    subject: str | None,
    body: str,
    author_actor: str,
    ulid: str | None = None,
) -> OutreachDraftVersionRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO outreach_draft_version "
        "(ulid, draft_id, version, subject, body, author_actor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ulid_value, draft_id, version, subject, body, author_actor),
    )
    row = conn.execute(
        f"SELECT {_VERSION_COLUMNS} FROM outreach_draft_version WHERE id = ?",
        (cur.lastrowid,),
    ).fetchone()
    return _version_row(row)


def list_draft_versions(
    conn: sqlite3.Connection, draft_id: int
) -> list[OutreachDraftVersionRecord]:
    rows = conn.execute(
        f"SELECT {_VERSION_COLUMNS} FROM outreach_draft_version "
        f"WHERE draft_id = ? ORDER BY version DESC",
        (draft_id,),
    ).fetchall()
    return [_version_row(r) for r in rows]


# ---------- messages ----------

_MESSAGE_COLUMNS = (
    "id, ulid, draft_id, partner_id, contact_log_id, sent_at, sent_via, "
    "recipient_handle, subject_snapshot, body_snapshot, version_sent"
)


def _message_row(row: sqlite3.Row) -> OutreachMessageRecord:
    return OutreachMessageRecord.model_validate(dict(row))


def insert_message(
    conn: sqlite3.Connection,
    *,
    draft_id: int,
    partner_id: int,
    contact_log_id: int,
    sent_via: str,
    recipient_handle: str | None,
    subject_snapshot: str | None,
    body_snapshot: str,
    version_sent: int,
    sent_at: datetime | None = None,
    ulid: str | None = None,
) -> OutreachMessageRecord:
    ulid_value = ulid or new_ulid()
    if sent_at is None:
        cur = conn.execute(
            "INSERT INTO outreach_message "
            "(ulid, draft_id, partner_id, contact_log_id, sent_via, recipient_handle, "
            "subject_snapshot, body_snapshot, version_sent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ulid_value, draft_id, partner_id, contact_log_id, sent_via,
             recipient_handle, subject_snapshot, body_snapshot, version_sent),
        )
    else:
        cur = conn.execute(
            "INSERT INTO outreach_message "
            "(ulid, draft_id, partner_id, contact_log_id, sent_at, sent_via, recipient_handle, "
            "subject_snapshot, body_snapshot, version_sent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ulid_value, draft_id, partner_id, contact_log_id, sent_at.isoformat(sep=" "),
             sent_via, recipient_handle, subject_snapshot, body_snapshot, version_sent),
        )
    row = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM outreach_message WHERE id = ?",
        (cur.lastrowid,),
    ).fetchone()
    return _message_row(row)


def get_message_by_ulid(
    conn: sqlite3.Connection, ulid: str
) -> OutreachMessageRecord | None:
    row = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM outreach_message WHERE ulid = ?", (ulid,)
    ).fetchone()
    return _message_row(row) if row else None


def list_messages(
    conn: sqlite3.Connection,
    *,
    partner_id: int | None = None,
    since: date | str | None = None,
    until: date | str | None = None,
    limit: int = 50,
) -> list[OutreachMessageRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if partner_id is not None:
        clauses.append("partner_id = ?")
        params.append(partner_id)
    if since is not None:
        clauses.append("date(sent_at) >= ?")
        params.append(str(since))
    if until is not None:
        clauses.append("date(sent_at) <= ?")
        params.append(str(until))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))
    rows = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM outreach_message {where} "
        f"ORDER BY sent_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_message_row(r) for r in rows]


def count_messages_in_window(
    conn: sqlite3.Connection, *, since: date | str, until: date | str
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM outreach_message WHERE date(sent_at) >= ? AND date(sent_at) <= ?",
        (str(since), str(until)),
    ).fetchone()
    return int(row["n"] or 0)


def count_messages_by_day(
    conn: sqlite3.Connection, *, since: date | str, until: date | str
) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT date(sent_at) AS d, COUNT(*) AS n FROM outreach_message "
        "WHERE date(sent_at) >= ? AND date(sent_at) <= ? "
        "GROUP BY date(sent_at) ORDER BY date(sent_at)",
        (str(since), str(until)),
    ).fetchall()
    return [(str(r["d"]), int(r["n"])) for r in rows]
