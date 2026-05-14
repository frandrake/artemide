"""/api/v1/admin routes — operational endpoints."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..services import ServiceContext, transaction
from ..services.system_service import SystemService
from .deps import get_context

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _backup_dir() -> Path:
    return Path(os.environ.get("ARTEMIDE_BACKUP_DIR", "/data/backups"))


@router.post("/backup")
def trigger_backup(ctx: ServiceContext = Depends(get_context)):
    script = Path(os.environ.get("ARTEMIDE_BACKUP_SCRIPT", "/app/scripts/backup.sh"))
    if not script.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="backup script unavailable",
        )
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    proc = subprocess.run(
        ["/bin/sh", str(script), timestamp],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"backup failed: {proc.stderr.strip()[:200]}",
        )
    filename = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else f"artemide-{timestamp}.db"
    return {"filename": filename, "actor": ctx.actor}


@router.get("/backups")
def list_backups(ctx: ServiceContext = Depends(get_context)):
    directory = _backup_dir()
    if not directory.exists():
        return {"backups": []}
    rows = []
    for p in sorted(directory.glob("artemide-*.db"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        st = p.stat()
        rows.append({
            "filename": p.name,
            "size_bytes": st.st_size,
            "modified_at": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
        })
    return {"backups": rows}


@router.post("/rotate-token")
def rotate_token(ctx: ServiceContext = Depends(get_context)):
    """Generate a fresh API token, persist to system_config, audit-log it.

    The response includes the new plaintext token *once*; subsequent
    reads only see it via the live auth check.
    """
    with transaction(ctx.conn):
        new_token = SystemService.rotate_api_token(ctx)
    return {
        "new_token": new_token,
        "message": (
            "Token rotated. Update your Claude MCP server header and any "
            "external tool configs now — the previous token is invalid."
        ),
    }
