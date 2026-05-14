"""FTS5 search index repository."""
from __future__ import annotations

import sqlite3
from typing import Any


def upsert_search_row(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_ulid: str,
    primary_text: str,
    secondary_text: str | None = None,
) -> None:
    conn.execute(
        "DELETE FROM search_index WHERE entity_type = ? AND entity_ulid = ?",
        (entity_type, entity_ulid),
    )
    conn.execute(
        "INSERT INTO search_index (entity_type, entity_ulid, primary_text, secondary_text) "
        "VALUES (?, ?, ?, ?)",
        (entity_type, entity_ulid, primary_text, secondary_text or ""),
    )


def delete_search_row(
    conn: sqlite3.Connection, *, entity_type: str, entity_ulid: str
) -> None:
    conn.execute(
        "DELETE FROM search_index WHERE entity_type = ? AND entity_ulid = ?",
        (entity_type, entity_ulid),
    )


def search(
    conn: sqlite3.Connection,
    *,
    query: str,
    entity_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = (
        "SELECT entity_type, entity_ulid, primary_text, secondary_text, "
        "bm25(search_index) AS rank "
        "FROM search_index WHERE search_index MATCH ?"
    )
    params: list[Any] = [query]
    if entity_type is not None:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    sql += " ORDER BY rank LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
