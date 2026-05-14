"""/api/v1/export routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response

from ..services import ServiceContext
from ..services.exceptions import ValidationError
from ..services.export_service import ExportService
from .deps import get_context

router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/markdown", response_class=PlainTextResponse)
def export_markdown(ctx: ServiceContext = Depends(get_context)) -> Response:
    body = ExportService.export_to_markdown(ctx)
    return Response(content=body, media_type="text/markdown; charset=utf-8")


@router.get("/csv", response_class=PlainTextResponse)
def export_csv(
    entity_type: str = Query(..., description="firm | partner | contact"),
    ctx: ServiceContext = Depends(get_context),
) -> Response:
    if entity_type not in {"firm", "partner", "contact"}:
        raise ValidationError(f"unsupported entity_type: {entity_type}")
    body = ExportService.export_to_csv(ctx, entity_type)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="artemide-{entity_type}s.csv"',
        },
    )
