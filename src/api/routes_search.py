"""/api/v1/search route."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from ..services import ServiceContext
from ..services.search_service import SearchService
from .deps import get_context

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(..., min_length=1, alias="q"),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    ctx: ServiceContext = Depends(get_context),
):
    hits = SearchService.search(ctx, query=q, entity_type=entity_type, limit=limit)
    return [asdict(h) for h in hits]
