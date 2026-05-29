"""Service layer.

Services hold all business logic. Transports (REST, MCP, CLI) call services;
services call repositories. Every mutation writes an audit_log entry.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal


Transport = Literal["mcp", "rest", "cli", "system", "web", "api"]
Role = Literal["owner", "bot"]


@dataclass
class ServiceContext:
    """Per-request context threaded through every service call."""
    conn: sqlite3.Connection
    actor: str = "FF"
    transport: Transport = "system"
    # v1.2 — owner/bot role (Rule 18). Cookie sessions, CLI and system tasks
    # are always 'owner'; only bot-role bearer tokens carry 'bot'.
    role: Role = "owner"


def assert_owner(ctx: "ServiceContext", *, operation: str) -> None:
    """Enforce Rule 18 at the service layer so every transport (REST, MCP) is
    covered. Audits the blocked attempt then raises ForbiddenRoleError."""
    if ctx.role != "owner":
        from ..models import AuditAction
        from .audit_service import AuditService
        from .exceptions import ForbiddenRoleError

        AuditService.record(
            ctx,
            action=AuditAction.denied,
            entity_type="auth",
            entity_ulid="forbidden_role",
            after={"actor": ctx.actor, "role": ctx.role, "operation": operation},
        )
        raise ForbiddenRoleError(f"owner role required: {operation}")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Reentrant BEGIN/COMMIT helper.

    `get_connection()` opens with isolation_level=None (autocommit); the
    outermost call issues BEGIN, nested calls use SAVEPOINTs so service
    methods compose cleanly when one calls another.
    """
    if conn.in_transaction:
        sp = f"sp_{id(object()):x}"
        conn.execute(f"SAVEPOINT {sp}")
        try:
            yield
        except BaseException:
            conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            conn.execute(f"RELEASE SAVEPOINT {sp}")
            raise
        else:
            conn.execute(f"RELEASE SAVEPOINT {sp}")
        return

    conn.execute("BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
