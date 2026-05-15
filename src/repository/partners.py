"""Partners repository — pure data access."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..models import FirmTier, PartnerRecord, RelationshipState
from ..ulid_helpers import new_ulid


_COLUMNS = (
    "id, ulid, firm_id, name, title, practice, seniority, location, introduced_via, email, linkedin_url, "
    "relationship_state, last_contact_date, next_touch_date, next_touch_topic, "
    "notes_summary, follow_ups_outstanding, created_at, updated_at, deleted_at, "
    "practice_focus, strategic_relevance, warm_intro_angle, thought_leadership, prior_career, ned_gateway, "
    "outreach_stage"
)


def _row_to_record(row: sqlite3.Row) -> PartnerRecord:
    return PartnerRecord.model_validate(dict(row))


def insert_partner(
    conn: sqlite3.Connection,
    *,
    firm_id: int,
    name: str,
    title: str | None = None,
    practice: str | None = None,
    seniority: str | None = None,
    email: str | None = None,
    linkedin_url: str | None = None,
    relationship_state: RelationshipState = RelationshipState.cold,
    last_contact_date: date | None = None,
    next_touch_date: date | None = None,
    next_touch_topic: str | None = None,
    notes_summary: str | None = None,
    ulid: str | None = None,
) -> PartnerRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO partners (ulid, firm_id, name, title, practice, seniority, email, linkedin_url, "
        "relationship_state, last_contact_date, next_touch_date, next_touch_topic, notes_summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, firm_id, name, title, practice, seniority, email, linkedin_url,
            relationship_state.value, last_contact_date, next_touch_date, next_touch_topic, notes_summary,
        ),
    )
    return get_partner_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_partner_by_id(conn: sqlite3.Connection, partner_id: int) -> PartnerRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM partners WHERE id = ?", (partner_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_partner_by_ulid(conn: sqlite3.Connection, ulid: str) -> PartnerRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM partners WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_partner_by_name(conn: sqlite3.Connection, firm_id: int, name: str) -> PartnerRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM partners WHERE firm_id = ? AND name = ?", (firm_id, name)
    ).fetchone()
    return _row_to_record(row) if row else None


def list_partners_by_firm(
    conn: sqlite3.Connection, firm_id: int, *, include_deleted: bool = False
) -> list[PartnerRecord]:
    clauses = ["firm_id = ?"]
    params: list[Any] = [firm_id]
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM partners WHERE {' AND '.join(clauses)} ORDER BY name", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_PARTNER_FIELDS = {
    "name", "title", "practice", "seniority", "location", "introduced_via",
    "email", "linkedin_url", "relationship_state", "last_contact_date",
    "next_touch_date", "next_touch_topic", "notes_summary", "follow_ups_outstanding",
    "practice_focus", "strategic_relevance", "warm_intro_angle",
    "thought_leadership", "prior_career", "ned_gateway",
    "outreach_stage",
}


def update_partner_fields(conn: sqlite3.Connection, partner_id: int, fields: dict[str, Any]) -> PartnerRecord | None:
    updates = {k: (v.value if hasattr(v, "value") else v) for k, v in fields.items() if k in _ALLOWED_PARTNER_FIELDS}
    if not updates:
        return get_partner_by_id(conn, partner_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE partners SET {assignments} WHERE id = ?",
        (*updates.values(), partner_id),
    )
    return get_partner_by_id(conn, partner_id)


def update_last_contact_date(conn: sqlite3.Connection, partner_id: int, contact_date: date) -> None:
    conn.execute(
        "UPDATE partners SET last_contact_date = ? "
        "WHERE id = ? AND (last_contact_date IS NULL OR last_contact_date < ?)",
        (contact_date, partner_id, contact_date),
    )


def soft_delete_partner(conn: sqlite3.Connection, partner_id: int) -> None:
    conn.execute(
        "UPDATE partners SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (partner_id,),
    )


def restore_partner(conn: sqlite3.Connection, partner_id: int) -> None:
    conn.execute("UPDATE partners SET deleted_at = NULL WHERE id = ?", (partner_id,))


def list_partners_with_due_touches(
    conn: sqlite3.Connection,
    *,
    window_days: int = 14,
    tier: FirmTier | None = None,
) -> list[PartnerRecord]:
    clauses = [
        "p.deleted_at IS NULL",
        "f.deleted_at IS NULL",
        "p.next_touch_date IS NOT NULL",
        "p.next_touch_date <= date('now', ? || ' days')",
    ]
    params: list[Any] = [f"+{int(window_days)}"]
    if tier is not None:
        clauses.append("f.tier = ?")
        params.append(tier.value)
    rows = conn.execute(
        f"SELECT {', '.join('p.' + c.strip() for c in _COLUMNS.split(','))} "
        f"FROM partners p JOIN firms f ON f.id = p.firm_id "
        f"WHERE {' AND '.join(clauses)} ORDER BY p.next_touch_date ASC",
        params,
    ).fetchall()
    return [_row_to_record(r) for r in rows]
