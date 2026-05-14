"""Shared helpers for MCP tool wrappers."""
from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from ..db import get_connection
from ..services import ServiceContext
from ..services.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger("artemide.mcp")


@contextmanager
def tool_session(name: str) -> Iterator[tuple[sqlite3.Connection, ServiceContext]]:
    """Open a DB connection + ServiceContext for the duration of one tool call.

    Logs tool name + duration only — never payloads.
    """
    started = time.perf_counter()
    conn = get_connection()
    try:
        yield conn, ServiceContext(conn=conn, actor="FF", transport="mcp")
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        log.info("mcp tool %s done in %.1fms", name, (time.perf_counter() - started) * 1000)


def error_response(exc: Exception) -> dict:
    """Convert service exceptions into the MCP error envelope."""
    if isinstance(exc, NotFoundError):
        code = "not_found"
    elif isinstance(exc, ConflictError):
        code = "conflict"
    elif isinstance(exc, InvalidStateTransitionError):
        code = "rule_violation"
    elif isinstance(exc, ValidationError):
        code = "validation_error"
    else:
        code = "internal_error"
    return {"ok": False, "error": code, "message": str(exc)}
