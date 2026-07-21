"""Persistence for owner feedback on derived Today recommendations."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..ulid_helpers import new_ulid


def list_feedback(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, ulid, source_key, workstream, disposition, snoozed_until, "
        "reason, created_at, updated_at FROM today_feedback"
    ).fetchall()
    return {r["source_key"]: dict(r) for r in rows}


def upsert_feedback(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    workstream: str,
    disposition: str,
    snoozed_until: date | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    existing = conn.execute(
        "SELECT id, ulid FROM today_feedback WHERE source_key = ?", (source_key,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE today_feedback SET workstream = ?, disposition = ?, "
            "snoozed_until = ?, reason = ? WHERE id = ?",
            (workstream, disposition, snoozed_until, reason, existing["id"]),
        )
        ulid = existing["ulid"]
    else:
        ulid = new_ulid()
        conn.execute(
            "INSERT INTO today_feedback "
            "(ulid, source_key, workstream, disposition, snoozed_until, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ulid, source_key, workstream, disposition, snoozed_until, reason),
        )
    row = conn.execute(
        "SELECT id, ulid, source_key, workstream, disposition, snoozed_until, "
        "reason, created_at, updated_at FROM today_feedback WHERE ulid = ?", (ulid,)
    ).fetchone()
    return dict(row)
