"""/api/v1/fit routes — engagement profile and rescoring."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import FitProfileInput
from ..services import ServiceContext
from ..services.exceptions import NotFoundError
from ..services.fit_service import FitService
from ._serde import to_response
from .deps import get_context

router = APIRouter(prefix="/api/v1/fit", tags=["fit"])


@router.get("/profile")
def get_profile(ctx: ServiceContext = Depends(get_context)):
    profile = FitService.get_active_profile(ctx.conn)
    if profile is None:
        raise NotFoundError("no active engagement profile")
    return to_response(profile)


@router.put("/profile")
def set_profile(body: FitProfileInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(FitService.set_active_profile(ctx, body))


@router.post("/rescore-all")
def rescore_all(ctx: ServiceContext = Depends(get_context)):
    count = FitService.rescore_all_owner(ctx)
    return {"rescored": count}
