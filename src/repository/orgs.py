"""Organisations repository — pure data access."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import OrganisationRecord
from ..ulid_helpers import new_ulid

_COLUMNS = (
    "id, ulid, name, sector, scale_band, hq_region, pertinence_note, "
    "watch_state, source, external_refs, created_at, updated_at, deleted_at"
)


def _val(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _row_to_record(row: sqlite3.Row) -> OrganisationRecord:
    return OrganisationRecord.model_validate(dict(row))


def insert_org(
    conn: sqlite3.Connection,
    *,
    name: str,
    sector: str | None = None,
    scale_band: Any = None,
    hq_region: str | None = None,
    pertinence_note: str | None = None,
    watch_state: Any = "watch",
    source: str | None = None,
    external_refs: str | None = None,
    ulid: str | None = None,
) -> OrganisationRecord:
    ulid_value = ulid or new_ulid()
    cur = conn.execute(
        "INSERT INTO organisations (ulid, name, sector, scale_band, hq_region, "
        "pertinence_note, watch_state, source, external_refs) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ulid_value, name, sector, _val(scale_band), hq_region,
            pertinence_note, _val(watch_state) or "watch", source, external_refs,
        ),
    )
    return get_org_by_id(conn, cur.lastrowid)  # type: ignore[arg-type]


def get_org_by_id(conn: sqlite3.Connection, org_id: int) -> OrganisationRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM organisations WHERE id = ?", (org_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_org_by_ulid(conn: sqlite3.Connection, ulid: str) -> OrganisationRecord | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM organisations WHERE ulid = ?", (ulid,)).fetchone()
    return _row_to_record(row) if row else None


def get_org_by_name(conn: sqlite3.Connection, name: str) -> OrganisationRecord | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM organisations WHERE name = ? AND deleted_at IS NULL",
        (name,),
    ).fetchone()
    return _row_to_record(row) if row else None


def list_orgs(
    conn: sqlite3.Connection,
    *,
    watch_state: Any = None,
    scale_band: Any = None,
    sector: str | None = None,
    include_deleted: bool = False,
) -> list[OrganisationRecord]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if watch_state is not None:
        clauses.append("watch_state = ?")
        params.append(_val(watch_state))
    if scale_band is not None:
        clauses.append("scale_band = ?")
        params.append(_val(scale_band))
    if sector is not None:
        clauses.append("sector = ?")
        params.append(sector)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM organisations {where} ORDER BY name", params
    ).fetchall()
    return [_row_to_record(r) for r in rows]


_ALLOWED_ORG_FIELDS = {
    "name", "sector", "scale_band", "hq_region", "pertinence_note",
    "watch_state", "source", "external_refs",
}


def update_org_fields(conn: sqlite3.Connection, org_id: int, fields: dict[str, Any]) -> OrganisationRecord | None:
    updates = {k: _val(v) for k, v in fields.items() if k in _ALLOWED_ORG_FIELDS}
    if not updates:
        return get_org_by_id(conn, org_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE organisations SET {assignments} WHERE id = ?",
        (*updates.values(), org_id),
    )
    return get_org_by_id(conn, org_id)


def soft_delete_org(conn: sqlite3.Connection, org_id: int) -> None:
    conn.execute(
        "UPDATE organisations SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
        (org_id,),
    )


def restore_org(conn: sqlite3.Connection, org_id: int) -> None:
    conn.execute("UPDATE organisations SET deleted_at = NULL WHERE id = ?", (org_id,))
