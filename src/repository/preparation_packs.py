"""Raw SQLite persistence for physically separate preparation-pack domains."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..ulid_helpers import new_ulid

_EXEC_PACK_COLUMNS = (
    "id, ulid, target_entity_type, target_entity_ulid, version, status, content, "
    "content_sha256, generated_by, model, prompt_version, generation_metadata, "
    "proposed_by, proposed_at, confirmed_by, confirmed_at, superseded_at"
)
_BOARD_PACK_COLUMNS = (
    "id, ulid, board_opportunity_ulid, version, status, content, content_sha256, "
    "generated_by, model, prompt_version, generation_metadata, proposed_by, "
    "proposed_at, confirmed_by, confirmed_at, superseded_at"
)
_SOURCE_COLUMNS = (
    "id, ulid, pack_id, source_kind, source_ulid, public_url, sha256, "
    "retrieved_at, citation_label, created_at"
)


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _insert_sources(
    conn: sqlite3.Connection, *, table: str, pack_id: int,
    sources: list[dict[str, Any]], created_at: str,
) -> None:
    for source in sources:
        conn.execute(
            f"INSERT INTO {table} "
            "(ulid, pack_id, source_kind, source_ulid, public_url, sha256, "
            "retrieved_at, citation_label, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_ulid(), pack_id, source["source_kind"], source.get("source_ulid"),
                source.get("public_url"), source["sha256"], source["retrieved_at"],
                source["citation_label"], created_at,
            ),
        )


def _sources(conn: sqlite3.Connection, *, table: str, pack_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {_SOURCE_COLUMNS} FROM {table} WHERE pack_id = ? ORDER BY id", (pack_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def insert_executive_pack(
    conn: sqlite3.Connection, *, target_entity_type: str, target_entity_ulid: str,
    content: str, content_sha256: str, generated_by: str, model: str | None,
    prompt_version: str | None, generation_metadata: dict[str, Any] | None,
    proposed_by: str, proposed_at: str, sources: list[dict[str, Any]],
) -> dict[str, Any]:
    version = int(conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM executive_preparation_pack "
        "WHERE target_entity_type = ? AND target_entity_ulid = ?",
        (target_entity_type, target_entity_ulid),
    ).fetchone()[0])
    ulid = new_ulid()
    cur = conn.execute(
        "INSERT INTO executive_preparation_pack "
        "(ulid, target_entity_type, target_entity_ulid, version, content, content_sha256, "
        "generated_by, model, prompt_version, generation_metadata, proposed_by, proposed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid, target_entity_type, target_entity_ulid, version, content, content_sha256,
            generated_by, model, prompt_version,
            json.dumps(generation_metadata, sort_keys=True) if generation_metadata is not None else None,
            proposed_by, proposed_at,
        ),
    )
    assert cur.lastrowid is not None
    _insert_sources(
        conn, table="executive_preparation_pack_source", pack_id=cur.lastrowid,
        sources=sources, created_at=proposed_at,
    )
    return get_executive_pack(conn, ulid)  # type: ignore[return-value]


def get_executive_pack(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {_EXEC_PACK_COLUMNS} FROM executive_preparation_pack WHERE ulid = ?", (ulid,)
    ).fetchone()
    pack = _dict(row)
    if pack is not None:
        pack["sources"] = _sources(
            conn, table="executive_preparation_pack_source", pack_id=pack["id"]
        )
    return pack


def list_executive_packs(
    conn: sqlite3.Connection, *, target_entity_type: str, target_entity_ulid: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {_EXEC_PACK_COLUMNS} FROM executive_preparation_pack "
        "WHERE target_entity_type = ? AND target_entity_ulid = ? ORDER BY version DESC",
        (target_entity_type, target_entity_ulid),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        pack = dict(row)
        pack["sources"] = _sources(
            conn, table="executive_preparation_pack_source", pack_id=pack["id"]
        )
        result.append(pack)
    return result


def confirm_executive_pack(
    conn: sqlite3.Connection, *, pack_id: int, target_entity_type: str,
    target_entity_ulid: str, actor: str, confirmed_at: str,
) -> None:
    conn.execute(
        "UPDATE executive_preparation_pack SET status = 'superseded', superseded_at = ? "
        "WHERE target_entity_type = ? AND target_entity_ulid = ? AND status = 'confirmed' AND id <> ?",
        (confirmed_at, target_entity_type, target_entity_ulid, pack_id),
    )
    conn.execute(
        "UPDATE executive_preparation_pack SET status = 'confirmed', confirmed_by = ?, confirmed_at = ? "
        "WHERE id = ? AND status = 'proposed'",
        (actor, confirmed_at, pack_id),
    )


def insert_board_pack(
    conn: sqlite3.Connection, *, board_opportunity_ulid: str, content: str,
    content_sha256: str, generated_by: str, model: str | None,
    prompt_version: str | None, generation_metadata: dict[str, Any] | None,
    proposed_by: str, proposed_at: str, sources: list[dict[str, Any]],
) -> dict[str, Any]:
    version = int(conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM board_preparation_pack "
        "WHERE board_opportunity_ulid = ?", (board_opportunity_ulid,),
    ).fetchone()[0])
    ulid = new_ulid()
    cur = conn.execute(
        "INSERT INTO board_preparation_pack "
        "(ulid, board_opportunity_ulid, version, content, content_sha256, generated_by, "
        "model, prompt_version, generation_metadata, proposed_by, proposed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid, board_opportunity_ulid, version, content, content_sha256, generated_by,
            model, prompt_version,
            json.dumps(generation_metadata, sort_keys=True) if generation_metadata is not None else None,
            proposed_by, proposed_at,
        ),
    )
    assert cur.lastrowid is not None
    _insert_sources(
        conn, table="board_preparation_pack_source", pack_id=cur.lastrowid,
        sources=sources, created_at=proposed_at,
    )
    return get_board_pack(conn, ulid)  # type: ignore[return-value]


def get_board_pack(conn: sqlite3.Connection, ulid: str) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {_BOARD_PACK_COLUMNS} FROM board_preparation_pack WHERE ulid = ?", (ulid,)
    ).fetchone()
    pack = _dict(row)
    if pack is not None:
        pack["sources"] = _sources(
            conn, table="board_preparation_pack_source", pack_id=pack["id"]
        )
    return pack


def list_board_packs(conn: sqlite3.Connection, *, board_opportunity_ulid: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {_BOARD_PACK_COLUMNS} FROM board_preparation_pack "
        "WHERE board_opportunity_ulid = ? ORDER BY version DESC", (board_opportunity_ulid,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        pack = dict(row)
        pack["sources"] = _sources(
            conn, table="board_preparation_pack_source", pack_id=pack["id"]
        )
        result.append(pack)
    return result


def confirm_board_pack(
    conn: sqlite3.Connection, *, pack_id: int, board_opportunity_ulid: str,
    actor: str, confirmed_at: str,
) -> None:
    conn.execute(
        "UPDATE board_preparation_pack SET status = 'superseded', superseded_at = ? "
        "WHERE board_opportunity_ulid = ? AND status = 'confirmed' AND id <> ?",
        (confirmed_at, board_opportunity_ulid, pack_id),
    )
    conn.execute(
        "UPDATE board_preparation_pack SET status = 'confirmed', confirmed_by = ?, confirmed_at = ? "
        "WHERE id = ? AND status = 'proposed'",
        (actor, confirmed_at, pack_id),
    )
