"""Data access for physically separated executive and board AI intake previews."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

from ..ulid_helpers import new_ulid

Domain = Literal["executive", "board"]
_TABLES: dict[Domain, str] = {
    "executive": "executive_ai_intake_preview",
    "board": "board_ai_intake_preview",
}
_JSON_FIELDS = ("proposed_payload", "corrected_payload", "sources", "provenance")


def _table(domain: Domain) -> str:
    return _TABLES[domain]


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for field in _JSON_FIELDS:
        if result.get(field) is not None:
            result[field] = json.loads(result[field])
    return result


def insert_preview(
    conn: sqlite3.Connection,
    *,
    domain: Domain,
    proposed_payload: dict[str, Any],
    provider: str,
    model: str,
    prompt: str,
    input_hash: str,
    sources: list[dict[str, Any]],
    provenance: dict[str, Any],
    created_by: str,
    ulid: str | None = None,
) -> dict[str, Any]:
    value = ulid or new_ulid()
    conn.execute(
        f"INSERT INTO {_table(domain)} "
        "(ulid, proposed_payload, provider, model, prompt, input_hash, sources, provenance, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            value,
            json.dumps(proposed_payload, sort_keys=True),
            provider,
            model,
            prompt,
            input_hash,
            json.dumps(sources, sort_keys=True),
            json.dumps(provenance, sort_keys=True),
            created_by,
        ),
    )
    record = get_preview_by_ulid(conn, domain=domain, ulid=value)
    assert record is not None
    return record


def get_preview_by_ulid(
    conn: sqlite3.Connection, *, domain: Domain, ulid: str
) -> dict[str, Any] | None:
    return _decode(conn.execute(f"SELECT * FROM {_table(domain)} WHERE ulid = ?", (ulid,)).fetchone())


def list_previews(
    conn: sqlite3.Connection, *, domain: Domain, status: str | None = None
) -> list[dict[str, Any]]:
    if status is None:
        rows = conn.execute(f"SELECT * FROM {_table(domain)} ORDER BY created_at DESC, id DESC").fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM {_table(domain)} WHERE status = ? ORDER BY created_at DESC, id DESC",
            (status,),
        ).fetchall()
    return [_decode(row) for row in rows if row is not None]  # type: ignore[misc]


def confirm_preview(
    conn: sqlite3.Connection,
    *,
    domain: Domain,
    preview_id: int,
    confirmed_by: str,
    corrected_payload: dict[str, Any] | None,
) -> bool:
    cursor = conn.execute(
        f"UPDATE {_table(domain)} SET status = 'confirmed', corrected_payload = ?, "
        "confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND status = 'draft'",
        (
            json.dumps(corrected_payload, sort_keys=True) if corrected_payload is not None else None,
            confirmed_by,
            preview_id,
        ),
    )
    return cursor.rowcount == 1


def reject_preview(
    conn: sqlite3.Connection,
    *,
    domain: Domain,
    preview_id: int,
    rejected_by: str,
    reason: str | None,
) -> bool:
    cursor = conn.execute(
        f"UPDATE {_table(domain)} SET status = 'rejected', rejected_by = ?, "
        "rejection_reason = ?, rejected_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND status = 'draft'",
        (rejected_by, reason, preview_id),
    )
    return cursor.rowcount == 1


def get_executive_preview_by_ulid(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    return get_preview_by_ulid(conn, domain="executive", ulid=ulid)


def get_board_preview_by_ulid(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    return get_preview_by_ulid(conn, domain="board", ulid=ulid)
