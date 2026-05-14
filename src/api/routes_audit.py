"""/api/v1/audit routes."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, Query

from ..repository import audit_log as audit_repo
from ..services import ServiceContext
from ..services.audit_service import AuditService
from ..services.exceptions import NotFoundError
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


def _dc(obj):
    if is_dataclass(obj):
        return {k: _dc(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc(i) for i in obj]
    return obj


@router.get("/report")
def get_report(ctx: ServiceContext = Depends(get_context)):
    return _dc(AuditService.generate_report(ctx))


@router.get("/log")
def list_log(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    ctx: ServiceContext = Depends(get_context),
):
    if entity_type and entity_id:
        return to_response_list(
            AuditService.list_by_entity(ctx, entity_type, entity_id, limit=limit)
        )
    if actor:
        return to_response_list(AuditService.list_by_actor(ctx, actor, limit=limit))
    return to_response_list(AuditService.list_recent(ctx, limit=limit))


@router.get("/log/{ulid}")
def get_audit_entry(ulid: str, ctx: ServiceContext = Depends(get_context)):
    entry = audit_repo.get_audit_by_ulid(ctx.conn, ulid)
    if entry is None:
        raise NotFoundError(f"audit entry not found: {ulid}")
    return to_response(entry)
