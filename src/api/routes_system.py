"""/api/v1/system info endpoint."""
from __future__ import annotations

import os
import platform
import sqlite3
from importlib import metadata
from pathlib import Path

from fastapi import APIRouter, Depends

from ..services import ServiceContext
from ..services.system_service import API_TOKEN_KEY, get_config
from .deps import get_context

router = APIRouter(prefix="/api/v1/system", tags=["system"])


_DEPENDENCIES = ("fastapi", "fastmcp", "pydantic", "uvicorn", "ulid-py", "itsdangerous")


def _safe_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "n/a"


def _count(conn: sqlite3.Connection, table: str, where: str = "1") -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])


@router.get("/info")
def system_info(ctx: ServiceContext = Depends(get_context)):
    schema_row = ctx.conn.execute(
        "SELECT version, applied_at FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    schema_version = schema_row["version"] if schema_row else None
    schema_applied_at = schema_row["applied_at"] if schema_row else None

    build_hash = "n/a"
    for candidate in ("/etc/artemide-build.txt", "/app/BUILD_HASH"):
        p = Path(candidate)
        if p.exists():
            build_hash = p.read_text().strip().splitlines()[0][:40]
            break

    token_source = "database" if get_config(ctx.conn, API_TOKEN_KEY) else "environment"

    counts = {
        "firms": _count(ctx.conn, "firms", "deleted_at IS NULL"),
        "partners": _count(ctx.conn, "partners", "deleted_at IS NULL"),
        "contacts": _count(ctx.conn, "contact_log"),
        "notes": _count(ctx.conn, "notes"),
        "audit_entries": _count(ctx.conn, "audit_log"),
    }

    deps = {name: _safe_version(name) for name in _DEPENDENCIES}
    deps["python"] = platform.python_version()
    deps["sqlite"] = sqlite3.sqlite_version

    return {
        "schema_version": schema_version,
        "schema_applied_at": schema_applied_at,
        "build_hash": build_hash,
        "token_source": token_source,
        "counts": counts,
        "dependencies": deps,
    }
