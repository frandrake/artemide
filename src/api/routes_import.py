"""/api/v1/import routes."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..services import ServiceContext
from ..services.import_service import ImportService
from .deps import get_context

router = APIRouter(prefix="/api/v1/import", tags=["import"])


class ImportInput(BaseModel):
    content: str
    overwrite_existing: bool = False


@router.post("/markdown")
def import_markdown(body: ImportInput, ctx: ServiceContext = Depends(get_context)):
    summary = ImportService.import_markdown(
        ctx, body.content, overwrite_existing=body.overwrite_existing
    )
    return asdict(summary)
