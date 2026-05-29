"""/api/v1/events routes — the outbox consumer interface (Rule 19)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..services import ServiceContext, assert_owner
from ..services.outbox_service import OutboxService
from ._serde import to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
def list_events(limit: int = Query(default=50, ge=1, le=500), ctx: ServiceContext = Depends(get_context)):
    return to_response_list(OutboxService.list_undelivered(ctx, limit=limit))


@router.get("/health")
def outbox_health(ctx: ServiceContext = Depends(get_context)):
    return OutboxService.health(ctx).model_dump(mode="json")


@router.post("/sweep")
def sweep_now(ctx: ServiceContext = Depends(get_context)):
    """Retry-now (Settings → Automation). Owner-only — bumps undelivered attempts."""
    assert_owner(ctx, operation="sweep outbox")
    bumped = OutboxService.sweep(ctx.conn)
    return {"bumped": bumped}


@router.post("/{ulid}/ack")
def ack_event(ulid: str, ctx: ServiceContext = Depends(get_context)):
    delivered = OutboxService.mark_delivered(ctx, ulid)
    return {"ulid": ulid, "delivered": delivered}
