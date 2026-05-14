"""/api/v1/admin routes."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..services import ServiceContext
from .deps import get_context

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


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
