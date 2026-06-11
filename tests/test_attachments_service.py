"""AttachmentsService — BLOB storage, mime/size guards, sha256 dedupe, no
content in records, bot may read but not delete."""
from __future__ import annotations

import sqlite3

import pytest

from src.models import AttachmentEntityType, AttachmentKind
from src.repository import engagements as engagements_repo
from src.repository import orgs as orgs_repo
from src.services import ServiceContext
from src.services.attachments_service import AttachmentsService
from src.services.exceptions import ForbiddenRoleError, NotFoundError, ValidationError

PDF = b"%PDF-1.4 a tiny document body"


def _ctx(db, role="owner", transport="cli"):
    return ServiceContext(conn=db, actor="FF", transport=transport, role=role)


def _seed_engagement(db):
    org = orgs_repo.insert_org(db, name="Acme Global")
    return engagements_repo.insert_engagement(db, org_id=org.id, role_title="CMO")


def _upload(ctx, eng, content=PDF, content_type="application/pdf", filename="spec.pdf",
            kind=AttachmentKind.job_spec):
    return AttachmentsService.upload(
        ctx, entity_type=AttachmentEntityType.engagement, entity_ulid=eng.ulid,
        kind=kind, filename=filename, content_type=content_type, content=content,
    )


def test_record_has_no_content_field(db):
    ctx = _ctx(db)
    rec = _upload(ctx, _seed_engagement(db))
    assert not hasattr(rec, "content")
    assert "content" not in rec.model_dump()


def test_bad_mime_and_oversize_raise_validation(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    with pytest.raises(ValidationError):
        _upload(ctx, eng, content_type="application/x-msdownload", filename="x.exe")
    with pytest.raises(ValidationError):
        AttachmentsService.upload(
            ctx, entity_type=AttachmentEntityType.engagement, entity_ulid=eng.ulid,
            kind=AttachmentKind.other, filename="big.pdf", content_type="application/pdf",
            content=b"x" * (26 * 1024 * 1024),
        )


def test_unknown_target_raises_not_found(db):
    ctx = _ctx(db)
    with pytest.raises(NotFoundError):
        AttachmentsService.upload(
            ctx, entity_type=AttachmentEntityType.engagement, entity_ulid="01NONEXISTENT0000000000000",
            kind=AttachmentKind.other, filename="a.pdf", content_type="application/pdf", content=PDF,
        )


def test_sha256_dedupe_returns_same_ulid_once(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    a1 = _upload(ctx, eng)
    a2 = _upload(ctx, eng)
    assert a1.ulid == a2.ulid
    # exactly one row, one audit, one outbox event
    assert db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action='attach'").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM events_outbox WHERE event_type='attachment.added'"
    ).fetchone()[0] == 1


def test_get_content_roundtrip_exact_bytes(db):
    ctx = _ctx(db)
    rec = _upload(ctx, _seed_engagement(db))
    content, content_type, filename = AttachmentsService.get_content(ctx, rec.ulid)
    assert content == PDF
    assert content_type == "application/pdf"
    assert filename == "spec.pdf"


def test_bot_can_upload_and_read_but_not_delete(db):
    owner = _ctx(db)
    eng = _seed_engagement(db)
    bot = _ctx(db, role="bot", transport="mcp")
    rec = _upload(bot, eng, content=b"bot bytes here", content_type="text/plain", filename="n.txt",
                  kind=AttachmentKind.reference)
    # bot reads content (Rule 22 dropped — no owner gate on content)
    content, _, _ = AttachmentsService.get_content(bot, rec.ulid)
    assert content == b"bot bytes here"
    # but delete is owner-only
    with pytest.raises(ForbiddenRoleError):
        AttachmentsService.soft_delete(bot, rec.ulid)
    owner_count = db.execute("SELECT COUNT(*) FROM attachments WHERE deleted_at IS NULL").fetchone()[0]
    assert owner_count == 1


def test_delete_and_restore(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    rec = _upload(ctx, eng)
    AttachmentsService.soft_delete(ctx, rec.ulid)
    assert AttachmentsService.list_by_entity(ctx, AttachmentEntityType.engagement, eng.ulid) == []
    with pytest.raises(NotFoundError):
        AttachmentsService.get_content(ctx, rec.ulid)
    AttachmentsService.restore(ctx, rec.ulid)
    assert len(AttachmentsService.list_by_entity(ctx, AttachmentEntityType.engagement, eng.ulid)) == 1


def test_blob_survives_sqlite_backup(db):
    """The blob-in-SQLite decision: bytes ride inside the DB file, so a
    `.backup` (the mechanism behind scripts/backup.sh) captures them."""
    ctx = _ctx(db)
    rec = _upload(ctx, _seed_engagement(db))
    backup = sqlite3.connect(":memory:", isolation_level=None)
    backup.row_factory = sqlite3.Row
    db.backup(backup)
    row = backup.execute("SELECT content FROM attachments WHERE ulid = ?", (rec.ulid,)).fetchone()
    assert bytes(row["content"]) == PDF
    backup.close()
