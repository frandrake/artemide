"""Contact log repository — append-only."""
from __future__ import annotations

import sqlite3
from datetime import date

from ..models import ContactChannel, ContactLogRecord, InitiatedBy
from ..ulid_helpers import new_ulid


_COLUMNS = (
    "id, ulid, partner_id, contact_date, channel, initiated_by, summary, "
    "value_given, value_received, follow_up, created_at"
)


def _row_to_record(row: sqlite3.Row) -> ContactLogRecord:
    return ContactLogRecord.model_validate(dict(row))


def insert_contact(
    conn: sqlite3.Connection,
    *,
    partner_id: int,
    contact_date: date,
    channel: ContactChannel,
    initiated_by: InitiatedBy,
    summary: str | None = None,
    value_given: str | None = None,
    value_received: str | None = None,
    follow_up: str | None = None,
    engagement_id: int | None = None,
    ulid: str | None = None,
) -> ContactLogRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO contact_log (ulid, partner_id, contact_date, channel, initiated_by, "
        "summary, value_given, value_received, follow_up, engagement_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, partner_id, contact_date, channel.value, initiated_by.value,
            summary, value_given, value_received, follow_up, engagement_id,
        ),
    )
    row = conn.execute(f"SELECT {_COLUMNS} FROM contact_log WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_record(row)


def get_contact_by_ulid(conn: sqlite3.Connection, ulid: str) -> ContactLogRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM contact_log WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def list_contacts_by_partner(
    conn: sqlite3.Connection, partner_id: int, *, limit: int | None = None
) -> list[ContactLogRecord]:
    sql = (
        f"SELECT {_COLUMNS} FROM contact_log WHERE partner_id = ? "
        f"ORDER BY contact_date DESC, id DESC"
    )
    params: tuple = (partner_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (partner_id, int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_record(r) for r in rows]


def list_contacts_by_firm(
    conn: sqlite3.Connection, firm_id: int, *, limit: int | None = None
) -> list[ContactLogRecord]:
    sql = (
        f"SELECT {', '.join('c.' + col.strip() for col in _COLUMNS.split(','))} "
        f"FROM contact_log c JOIN partners p ON p.id = c.partner_id "
        f"WHERE p.firm_id = ? ORDER BY c.contact_date DESC, c.id DESC"
    )
    params: tuple = (firm_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (firm_id, int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_record(r) for r in rows]


def list_recent_contacts(conn: sqlite3.Connection, *, limit: int = 50) -> list[ContactLogRecord]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM contact_log ORDER BY contact_date DESC, id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def count_value_given_received(conn: sqlite3.Connection, partner_id: int) -> tuple[int, int]:
    row = conn.execute(
        "SELECT "
        "SUM(CASE WHEN value_given IS NOT NULL AND value_given <> '' THEN 1 ELSE 0 END) AS given, "
        "SUM(CASE WHEN value_received IS NOT NULL AND value_received <> '' THEN 1 ELSE 0 END) AS received "
        "FROM contact_log WHERE partner_id = ?",
        (partner_id,),
    ).fetchone()
    return (int(row["given"] or 0), int(row["received"] or 0))


def is_duplicate_contact(
    conn: sqlite3.Connection, partner_id: int, contact_date: date, channel: ContactChannel
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM contact_log WHERE partner_id = ? AND contact_date = ? AND channel = ? LIMIT 1",
        (partner_id, contact_date, channel.value),
    ).fetchone()
    return row is not None


def count_contacts_in_window(
    conn: sqlite3.Connection,
    *,
    initiated_by: InitiatedBy | str | None = None,
    since: date | str,
    until: date | str,
) -> int:
    clauses = ["contact_date >= ?", "contact_date <= ?"]
    params: list = [str(since), str(until)]
    if initiated_by is not None:
        clauses.append("initiated_by = ?")
        params.append(initiated_by.value if hasattr(initiated_by, "value") else initiated_by)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM contact_log WHERE {' AND '.join(clauses)}",
        params,
    ).fetchone()
    return int(row["n"] or 0)


def count_contacts_by_day(
    conn: sqlite3.Connection,
    *,
    initiated_by: InitiatedBy | str | None = None,
    since: date | str,
    until: date | str,
) -> list[tuple[str, int]]:
    clauses = ["contact_date >= ?", "contact_date <= ?"]
    params: list = [str(since), str(until)]
    if initiated_by is not None:
        clauses.append("initiated_by = ?")
        params.append(initiated_by.value if hasattr(initiated_by, "value") else initiated_by)
    rows = conn.execute(
        f"SELECT contact_date AS d, COUNT(*) AS n FROM contact_log "
        f"WHERE {' AND '.join(clauses)} GROUP BY contact_date ORDER BY contact_date",
        params,
    ).fetchall()
    return [(str(r["d"]), int(r["n"])) for r in rows]
