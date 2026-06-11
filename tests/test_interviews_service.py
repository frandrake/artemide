"""InterviewsService — paired log row, searchable transcript, audit/outbox,
owner-only soft delete."""
from __future__ import annotations

import json
from datetime import date

import pytest

from src.models import (
    InterviewFormat,
    InterviewUpdateInput,
    LogInterviewInput,
    SetTranscriptInput,
    TranscriptSource,
)
from src.repository import engagements as engagements_repo
from src.repository import orgs as orgs_repo
from src.repository import search_index as search_repo
from src.services import ServiceContext
from src.services.exceptions import ForbiddenRoleError
from src.services.interviews_service import InterviewsService


def _ctx(db, role="owner", transport="cli"):
    return ServiceContext(conn=db, actor="FF", transport=transport, role=role)


def _seed_engagement(db):
    org = orgs_repo.insert_org(db, name="Acme Global")
    return engagements_repo.insert_engagement(db, org_id=org.id, role_title="CMO")


def test_log_writes_linked_engagement_log_row(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(), round="first",
        format=InterviewFormat.video, summary="strong on strategy",
    ))
    assert iv.engagement_log_id is not None
    logs = engagements_repo.list_log(db, eng.id)
    interview_logs = [l for l in logs if l.event_type.value == "interview"]
    assert len(interview_logs) == 1
    assert interview_logs[0].id == iv.engagement_log_id


def test_transcript_is_searchable_but_omitted_from_metadata(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(),
        summary="notes", transcript="candidate discussed quantum widgets at length",
    ))
    hits = search_repo.search(db, query="quantum")
    assert any(h["entity_ulid"] == iv.ulid for h in hits)

    # list_by_engagement returns metadata only (no transcript body)
    meta = InterviewsService.list_by_engagement(ctx, eng.ulid)
    assert meta[0].transcript is None
    # get() honours include_transcript
    assert InterviewsService.get(ctx, iv.ulid).transcript is None
    assert "quantum" in InterviewsService.get(ctx, iv.ulid, include_transcript=True).transcript


def test_audit_after_excludes_transcript_body(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(),
        transcript="SENSITIVE VERBATIM TEXT",
    ))
    row = db.execute(
        "SELECT payload FROM audit_log WHERE entity_type='interview' AND action='interview' "
        "AND entity_id=?", (iv.ulid,),
    ).fetchone()
    assert row is not None
    assert "SENSITIVE VERBATIM TEXT" not in (row["payload"] or "")
    after = json.loads(row["payload"])["after"]
    assert "transcript" not in after


def test_outbox_emits_logged_and_transcript_added(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(), transcript="t",
    ))
    types = {r["event_type"] for r in db.execute(
        "SELECT event_type FROM events_outbox WHERE entity_type='interview'"
    ).fetchall()}
    assert "interview.logged" in types
    assert "interview.transcript_added" in types


def test_set_transcript_then_searchable(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(), summary="round one",
    ))
    InterviewsService.set_transcript(ctx, SetTranscriptInput(
        interview_ulid=iv.ulid, transcript="zebra crossing analogy",
        transcript_source=TranscriptSource.manual,
    ))
    hits = search_repo.search(db, query="zebra")
    assert any(h["entity_ulid"] == iv.ulid for h in hits)


def test_update_fields(db):
    ctx = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(ctx, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(), round="first",
    ))
    updated = InterviewsService.update_fields(ctx, iv.ulid, InterviewUpdateInput(round="final", panel="CEO"))
    assert updated.round == "final"
    assert updated.panel == "CEO"


def test_soft_delete_is_owner_only(db):
    owner = _ctx(db)
    eng = _seed_engagement(db)
    iv = InterviewsService.log(owner, LogInterviewInput(
        engagement_ulid=eng.ulid, interview_date=date.today(),
    ))
    bot = _ctx(db, role="bot", transport="mcp")
    with pytest.raises(ForbiddenRoleError):
        InterviewsService.soft_delete(bot, iv.ulid)
    # the blocked attempt is audited as 'denied'
    denied = db.execute("SELECT COUNT(*) FROM audit_log WHERE action='denied'").fetchone()[0]
    assert denied >= 1
    # owner can delete + restore
    InterviewsService.soft_delete(owner, iv.ulid)
    assert InterviewsService.list_by_engagement(owner, eng.ulid) == []
    InterviewsService.restore(owner, iv.ulid)
    assert len(InterviewsService.list_by_engagement(owner, eng.ulid)) == 1
