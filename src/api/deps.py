"""Shared FastAPI dependencies."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterator

from fastapi import Depends, Header, Request, Response

from ..auth import auth_dependency
from ..db import get_connection
from ..models import AuditAction
from ..services import ServiceContext
from ..services.exceptions import ForbiddenRoleError


_IDEMPOTENCY_TTL_HOURS = 24


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_identity(request: Request) -> tuple[str, str]:
    return auth_dependency(request)


def get_context(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    identity: tuple[str, str] = Depends(get_identity),
) -> ServiceContext:
    actor, role = identity
    return ServiceContext(conn=conn, actor=actor, transport="rest", role=role)


def require_owner(ctx: ServiceContext = Depends(get_context)) -> ServiceContext:
    """Gate an endpoint to owner-role callers (Rule 18). Audits and 403s a bot."""
    if ctx.role != "owner":
        from ..services.audit_service import AuditService

        AuditService.record(
            ctx,
            action=AuditAction.denied,
            entity_type="auth",
            entity_ulid="forbidden_role",
            after={"actor": ctx.actor, "role": ctx.role},
        )
        raise ForbiddenRoleError("owner role required for this operation")
    return ctx


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


def prune_expired_idempotency_keys(conn: sqlite3.Connection) -> int:
    """Delete idempotency keys past their TTL so the cache (which stores full
    response bodies) doesn't grow unbounded. Returns rows deleted."""
    cur = conn.execute(
        "DELETE FROM idempotency_keys WHERE expires_at < CURRENT_TIMESTAMP"
    )
    return cur.rowcount
