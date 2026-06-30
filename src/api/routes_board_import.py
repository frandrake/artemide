"""/api/v1/board/import routes — seed the board ledger (tiered firms/contacts)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from ..models import ImportBoardMarkdownInput
from ..services import ServiceContext
from ..services.board_import_service import BoardImportService
from .deps import get_context

router = APIRouter(prefix="/api/v1/board/import", tags=["board"])


@router.post("/markdown")
def import_board_markdown(body: ImportBoardMarkdownInput, ctx: ServiceContext = Depends(get_context)):
    return asdict(BoardImportService.import_markdown(ctx, body.body))
