"""/api/v1/attachments routes — file upload/download backed by SQLite BLOBs."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from ..models import AttachmentEntityType, AttachmentKind
from ..services import ServiceContext
from ..services.attachments_service import AttachmentsService
from ._serde import to_response, to_response_list
from .deps import get_context

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])


def _content_disposition(filename: str) -> str:
    """Build a safe Content-Disposition. Strips quotes/newlines from the ASCII
    fallback and adds an RFC 5987 filename* for non-ASCII names."""
    ascii_name = "".join(c for c in filename if 32 <= ord(c) < 127 and c not in '"\\').strip()
    ascii_name = ascii_name.replace("\r", "").replace("\n", "") or "download"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


@router.get("")
def list_attachments(
    entity_type: AttachmentEntityType = Query(...),
    entity_ulid: str = Query(...),
    ctx: ServiceContext = Depends(get_context),
):
    return to_response_list(AttachmentsService.list_by_entity(ctx, entity_type, entity_ulid))


@router.post("")
async def upload_attachment(
    file: UploadFile = File(...),
    entity_type: AttachmentEntityType = Form(...),
    entity_ulid: str = Form(...),
    kind: AttachmentKind = Form(...),
    ctx: ServiceContext = Depends(get_context),
):
    content = await file.read()
    rec = AttachmentsService.upload(
        ctx,
        entity_type=entity_type,
        entity_ulid=entity_ulid,
        kind=kind,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return to_response(rec)


@router.get("/{ulid}")
def get_attachment(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(AttachmentsService.get_metadata(ctx, ulid))


@router.get("/{ulid}/content")
def get_attachment_content(ulid: str, ctx: ServiceContext = Depends(get_context)):
    content, content_type, filename = AttachmentsService.get_content(ctx, ulid)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.delete("/{ulid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(ulid: str, ctx: ServiceContext = Depends(get_context)) -> None:
    AttachmentsService.soft_delete(ctx, ulid)


@router.post("/{ulid}/restore")
def restore_attachment(ulid: str, ctx: ServiceContext = Depends(get_context)):
    return to_response(AttachmentsService.restore(ctx, ulid))
