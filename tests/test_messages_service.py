"""MessagesService — Rule 17 (owner-only approve) and Rule 20 (idempotency)."""
from __future__ import annotations

import pytest

from src.models import MessageStatus, ProposeMessageInput
from src.repository import messages as messages_repo
from src.repository import outbox as outbox_repo
from src.services import ServiceContext
from src.services.exceptions import ForbiddenRoleError
from src.services.messages_service import MessagesService


def _ctx(db, role="owner"):
    return ServiceContext(conn=db, actor="FF" if role == "owner" else "n8n_bot", transport="rest", role=role)


def _propose(ctx, **kw):
    data = {"body": "Hello, following up.", **kw}
    return MessagesService.propose(ctx, ProposeMessageInput(**data))


def test_propose_lands_as_proposed(db):
    m = _propose(_ctx(db, "bot"))
    assert m.status == MessageStatus.proposed
    assert m.created_by_transport == "rest"


def test_bot_cannot_approve_and_attempt_is_audited(db):
    bot = _ctx(db, "bot")
    m = _propose(bot)
    with pytest.raises(ForbiddenRoleError):
        MessagesService.approve(bot, m.ulid)
    # status unchanged
    assert MessagesService.get_by_ulid(bot, m.ulid).status == MessageStatus.proposed
    # the blocked attempt is audited (action='denied')
    denied = db.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'denied'").fetchone()[0]
    assert denied >= 1
    # and no message.approved event was emitted
    assert not any(e.event_type == "message.approved" for e in outbox_repo.list_undelivered(db))


def test_owner_approve_emits_event(db):
    owner = _ctx(db, "owner")
    m = _propose(owner)
    approved = MessagesService.approve(owner, m.ulid)
    assert approved.status == MessageStatus.approved
    assert approved.approved_at is not None
    assert any(e.event_type == "message.approved" and e.entity_ulid == m.ulid
               for e in outbox_repo.list_undelivered(db))


def test_mark_sent_requires_approval(db):
    owner = _ctx(db, "owner")
    m = _propose(owner)
    from src.services.exceptions import ConflictError
    with pytest.raises(ConflictError):
        MessagesService.mark_sent(owner, m.ulid)  # not approved yet
    MessagesService.approve(owner, m.ulid)
    sent = MessagesService.mark_sent(_ctx(db, "bot"), m.ulid)  # n8n marks sent (bot allowed)
    assert sent.status == MessageStatus.sent
    assert sent.sent_at is not None


def test_source_ref_idempotency(db):
    owner = _ctx(db, "owner")
    first = _propose(owner, source_ref="mail-123")
    second = _propose(owner, source_ref="mail-123")
    assert first.ulid == second.ulid
    rows = messages_repo.list_messages(db)
    assert len([r for r in rows if r.source_ref == "mail-123"]) == 1


def test_bot_cannot_edit_or_discard(db):
    owner = _ctx(db, "owner")
    bot = _ctx(db, "bot")
    m = _propose(owner)
    from src.models import MessageEditInput
    with pytest.raises(ForbiddenRoleError):
        MessagesService.edit(bot, m.ulid, MessageEditInput(body="changed"))
    with pytest.raises(ForbiddenRoleError):
        MessagesService.discard(bot, m.ulid)
