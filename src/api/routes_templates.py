"""/api/v1/templates routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from ..models import (
    OutreachChannel,
    TemplateCreateInput,
    TemplateRenderInput,
    TemplateUpdateInput,
)
from ..services import ServiceContext
from ..services.templates_service import TemplatesService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("")
def list_templates(
    channel: OutreachChannel | None = Query(default=None),
    category: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_context),
):
    items = TemplatesService.list(
        ctx, channel=channel, category=category, include_deleted=include_deleted
    )
    return to_response_list(items)


@router.post("")
def create_template(body: TemplateCreateInput, ctx: ServiceContext = Depends(get_context)):
    return to_response(TemplatesService.create(ctx, body))


@router.get("/{ulid}")
def get_template(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(TemplatesService.get_by_ulid(ctx, ulid))


@router.patch("/{ulid}")
def patch_template(
    ulid: str, body: TemplateUpdateInput, ctx: ServiceContext = Depends(get_context)
):
    return to_response(TemplatesService.update(ctx, ulid, body))


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    TemplatesService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_template(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(TemplatesService.restore(ctx, ulid))


@router.post("/{ulid}/render")
def render_template(
    ulid: str, body: TemplateRenderInput, ctx: ServiceContext = Depends(get_context)
):
    return TemplatesService.render(
        ctx,
        template_ulid=ulid,
        partner_ulid=body.partner_ulid,
        overrides=body.overrides,
    )
