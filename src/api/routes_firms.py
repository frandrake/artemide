"""/api/v1/firms routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from ..models import FirmTier, FirmUpdateInput, RelationshipState
from ..services import ServiceContext
from ..services.firms_service import FirmsService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/firms", tags=["firms"])


@router.get("")
def list_firms(
    tier: FirmTier | None = Query(default=None),
    state: RelationshipState | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    firms = FirmsService.list(ctx, tier=tier, state=state, include_deleted=include_deleted)
    return to_response_list(firms)


@router.get("/{ulid}")
def get_firm(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(FirmsService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_firm(ulid: str, body: FirmUpdateInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(FirmsService.update_fields(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    FirmsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_firm(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(FirmsService.restore(ctx, ulid))
