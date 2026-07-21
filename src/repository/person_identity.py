"""Neutral person identity and explicit workstream-link data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..ulid_helpers import new_ulid

_IDENTITY_COLUMNS = (
    "id, ulid, display_name, preferred_name, email, linkedin_url, current_title, "
    "current_organisation, location, source_url, created_at, updated_at"
)
_ALLOWED_FIELDS = {
    "display_name",
    "preferred_name",
    "email",
    "linkedin_url",
    "current_title",
    "current_organisation",
    "location",
    "source_url",
}


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def insert_identity(
    conn: sqlite3.Connection,
    *,
    display_name: str,
    preferred_name: str | None = None,
    email: str | None = None,
    linkedin_url: str | None = None,
    current_title: str | None = None,
    current_organisation: str | None = None,
    location: str | None = None,
    source_url: str | None = None,
    ulid: str | None = None,
) -> dict[str, Any]:
    value = ulid or new_ulid()
    conn.execute(
        "INSERT INTO person_identity "
        "(ulid, display_name, preferred_name, email, linkedin_url, current_title, "
        "current_organisation, location, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            value,
            display_name,
            preferred_name,
            email,
            linkedin_url,
            current_title,
            current_organisation,
            location,
            source_url,
        ),
    )
    record = get_identity_by_ulid(conn, value)
    assert record is not None
    return record


def get_identity_by_id(conn: sqlite3.Connection, identity_id: int) -> dict[str, Any] | None:
    return _dict(
        conn.execute(
            f"SELECT {_IDENTITY_COLUMNS} FROM person_identity WHERE id = ?", (identity_id,)
        ).fetchone()
    )


def get_identity_by_ulid(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    return _dict(
        conn.execute(
            f"SELECT {_IDENTITY_COLUMNS} FROM person_identity WHERE ulid = ?", (ulid,)
        ).fetchone()
    )


def list_identities(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {_IDENTITY_COLUMNS} FROM person_identity ORDER BY display_name, ulid"
    ).fetchall()
    return [dict(row) for row in rows]


def update_identity_fields(
    conn: sqlite3.Connection, identity_id: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    updates = {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS}
    if updates:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE person_identity SET {assignments} WHERE id = ?",
            (*updates.values(), identity_id),
        )
    return get_identity_by_id(conn, identity_id)


def insert_executive_link(
    conn: sqlite3.Connection, *, person_identity_id: int, partner_id: int, linked_by: str
) -> dict[str, Any]:
    ulid = new_ulid()
    conn.execute(
        "INSERT INTO executive_person_link "
        "(ulid, person_identity_id, partner_id, linked_by) VALUES (?, ?, ?, ?)",
        (ulid, person_identity_id, partner_id, linked_by),
    )
    return dict(
        conn.execute("SELECT * FROM executive_person_link WHERE ulid = ?", (ulid,)).fetchone()
    )


def insert_board_link(
    conn: sqlite3.Connection,
    *,
    person_identity_id: int,
    board_contact_id: int,
    linked_by: str,
) -> dict[str, Any]:
    ulid = new_ulid()
    conn.execute(
        "INSERT INTO board_person_link "
        "(ulid, person_identity_id, board_contact_id, linked_by) VALUES (?, ?, ?, ?)",
        (ulid, person_identity_id, board_contact_id, linked_by),
    )
    return dict(conn.execute("SELECT * FROM board_person_link WHERE ulid = ?", (ulid,)).fetchone())


def list_partner_ulids(conn: sqlite3.Connection, person_identity_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT p.ulid FROM executive_person_link l "
        "JOIN partners p ON p.id = l.partner_id "
        "WHERE l.person_identity_id = ? ORDER BY p.ulid",
        (person_identity_id,),
    ).fetchall()
    return [row[0] for row in rows]


def list_board_contact_ulids(conn: sqlite3.Connection, person_identity_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT c.ulid FROM board_person_link l "
        "JOIN board_contact c ON c.id = l.board_contact_id "
        "WHERE l.person_identity_id = ? ORDER BY c.ulid",
        (person_identity_id,),
    ).fetchall()
    return [row[0] for row in rows]


def delete_executive_link(
    conn: sqlite3.Connection, *, person_identity_id: int, partner_id: int
) -> bool:
    cursor = conn.execute(
        "DELETE FROM executive_person_link WHERE person_identity_id = ? AND partner_id = ?",
        (person_identity_id, partner_id),
    )
    return cursor.rowcount > 0


def delete_board_link(
    conn: sqlite3.Connection, *, person_identity_id: int, board_contact_id: int
) -> bool:
    cursor = conn.execute(
        "DELETE FROM board_person_link WHERE person_identity_id = ? AND board_contact_id = ?",
        (person_identity_id, board_contact_id),
    )
    return cursor.rowcount > 0
