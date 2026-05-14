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
    action: str | None = Query(default=None),
    transport: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: ServiceContext = Depends(get_context),
):
    # Lightweight filtered list directly via SQL — keeps the audit
    # repository focused while still serving the explorer UI.
    where: list[str] = []
    params: list[object] = []
    if entity_type:
        where.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        where.append("entity_id = ?")
        params.append(entity_id)
    if actor:
        where.append("actor = ?")
        params.append(actor)
    if action:
        where.append("action = ?")
        params.append(action)
    if transport:
        where.append("transport = ?")
        params.append(transport)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = ctx.conn.execute(
        "SELECT id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp "
        f"FROM audit_log {clause} ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
        (*params, int(limit), int(offset)),
    ).fetchall()
    from ..models import AuditLogRecord
    return to_response_list([AuditLogRecord.model_validate(dict(r)) for r in rows])


@router.get("/log/{ulid}")
def get_audit_entry(ulid: str, ctx: ServiceContext = Depends(get_context)):
    entry = audit_repo.get_audit_by_ulid(ctx.conn, ulid)
    if entry is None:
        raise NotFoundError(f"audit entry not found: {ulid}")
    return to_response(entry)
