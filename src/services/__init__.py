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


@dataclass
class ServiceContext:
    """Per-request context threaded through every service call."""
    conn: sqlite3.Connection
    actor: str = "FF"
    transport: Transport = "system"


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
