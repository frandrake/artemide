"""/api/v1/board/export routes — per-domain board export (kept apart from exec)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response

from ..services import ServiceContext
from ..services.board_export_service import BoardExportService
from ..services.exceptions import ValidationError
from .deps import get_context

router = APIRouter(prefix="/api/v1/board/export", tags=["board"])

_CSV_ENTITIES = {"board_firm", "board_contact", "board_opportunity", "board_evaluation"}


@router.get("/markdown", response_class=PlainTextResponse)
def export_board_markdown(ctx: ServiceContext = Depends(get_context)) -> Response:
    body = BoardExportService.export_to_markdown(ctx)
    return Response(content=body, media_type="text/markdown; charset=utf-8")


@router.get("/csv", response_class=PlainTextResponse)
def export_board_csv(
    entity_type: str = Query(..., description="board_firm | board_contact | board_opportunity | board_evaluation"),
    ctx: ServiceContext = Depends(get_context),
) -> Response:
    if entity_type not in _CSV_ENTITIES:
        raise ValidationError(f"unsupported entity_type: {entity_type}")
    body = BoardExportService.export_to_csv(ctx, entity_type)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="artemide-{entity_type}.csv"'},
    )
