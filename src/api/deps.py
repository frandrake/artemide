"""Shared FastAPI dependencies."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterator

from fastapi import Depends, Header, Request, Response

from ..auth import auth_dependency
from ..db import get_connection
from ..services import ServiceContext


_IDEMPOTENCY_TTL_HOURS = 24


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_actor(request: Request) -> str:
    return auth_dependency(request)


def get_context(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    actor: str = Depends(get_actor),
) -> ServiceContext:
    return ServiceContext(conn=conn, actor=actor, transport="rest")


def lookup_idempotent_response(
    conn: sqlite3.Connection, key: str | None
) -> Response | None:
    if not key:
        return None
    row = conn.execute(
        "SELECT response_body, response_status FROM idempotency_keys "
        "WHERE key = ? AND expires_at > CURRENT_TIMESTAMP",
        (key,),
    ).fetchone()
    if row is None:
        return None
    return Response(
        content=row["response_body"] or "",
        status_code=int(row["response_status"] or 200),
        media_type="application/json",
    )


def store_idempotent_response(
    conn: sqlite3.Connection,
    key: str | None,
    body: Any,
    status_code: int = 200,
) -> None:
    if not key:
        return
    expires_at = (datetime.utcnow() + timedelta(hours=_IDEMPOTENCY_TTL_HOURS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    serialised = body if isinstance(body, str) else json.dumps(body, default=str)
    conn.execute(
        "INSERT OR REPLACE INTO idempotency_keys (key, response_body, response_status, expires_at) "
        "VALUES (?, ?, ?, ?)",
        (key, serialised, status_code, expires_at),
    )


def idempotency_key_header(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    return idempotency_key
