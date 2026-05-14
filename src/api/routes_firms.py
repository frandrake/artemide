"""/api/v1/firms routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from ..models import FirmTier, RelationshipState
from ..services import ServiceContext
from ..services.firms_service import FirmsService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/firms", tags=["firms"])


class FirmPatch(BaseModel):
    relationship_state: RelationshipState | None = None
    notes_summary: str | None = None


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
def patch_firm(ulid: str, patch: FirmPatch, ctx: ServiceContext = Depends(get_context)):
    firm = FirmsService.get_by_ulid(ctx, ulid)
    if patch.relationship_state is not None:
        firm = FirmsService.update_state(ctx, ulid, patch.relationship_state)
    if patch.notes_summary is not None:
        firm = FirmsService.update_notes(ctx, ulid, patch.notes_summary)
    return to_response(firm)


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    FirmsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_firm(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(FirmsService.restore(ctx, ulid))
