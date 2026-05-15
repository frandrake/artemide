"""Tests for the Phase-11 outreach workspace.

Engagement calendar, templates + rendering, drafts + versions,
and the atomic mark_sent transaction.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.models import (
    EngagementCalendarUpdateInput,
    EngagementStatus,
    FirmTier,
    OutreachChannel,
    OutreachDraftCreateInput,
    OutreachDraftUpdateInput,
    OutreachSendInput,
    OutreachStage,
    TemplateCreateInput,
)
from src.repository import contacts as contacts_repo
from src.repository import engagement_calendar as eng_repo
from src.repository import firms as firms_repo
from src.repository import outreach as outreach_repo
from src.repository import partners as partners_repo
from src.repository import templates as templates_repo
from src.services import ServiceContext
from src.services.engagement_service import EngagementService
from src.services.exceptions import ConflictError, NotFoundError, ValidationError
from src.services.outreach_service import OutreachService
from src.services.template_render import build_context, render
from src.services.templates_service import TemplatesService


def _ctx(conn):
    return ServiceContext(conn=conn, actor="FF", transport="system")


def _seed(conn):
    firm = firms_repo.insert_firm(
        conn, name="Test Search Co", tier=FirmTier.specialist, region="London"
    )
    partner = partners_repo.insert_partner(
        conn, firm_id=firm.id, name="Test Partner",
    )
    return firm, partner


# ---------- Template renderer ----------

def test_render_simple_substitution():
    ctx = {"partner.name": "Alice", "firm.name": "BigCo"}
    out, missing, used = render("Hi {{partner.name}} at {{firm.name}}!", ctx)
    assert out == "Hi Alice at BigCo!"
    assert missing == []
    assert used == {"partner.name": "Alice", "firm.name": "BigCo"}


def test_render_missing_variable_records_but_emits_empty():
    out, missing, _ = render("Hi {{partner.name}}, re {{partner.warm_intro_angle}}.", {
        "partner.name": "Alice", "partner.warm_intro_angle": None,
    })
    assert out == "Hi Alice, re ."
    assert missing == ["partner.warm_intro_angle"]


def test_render_conditional_block_present():
    out, _, _ = render(
        "Hi.{{#partner.warm_intro_angle}} Specifically: {{partner.warm_intro_angle}}.{{/partner.warm_intro_angle}}",
        {"partner.warm_intro_angle": "Chicago Booth alumni"},
    )
    assert out == "Hi. Specifically: Chicago Booth alumni."


def test_render_conditional_block_absent():
    out, missing, _ = render(
        "Hi.{{#partner.warm_intro_angle}} Specifically: {{partner.warm_intro_angle}}.{{/partner.warm_intro_angle}}",
        {"partner.warm_intro_angle": None},
    )
    assert out == "Hi."
    # Conditional strip means the inner var is never substituted, so not missing
    assert missing == []


def test_render_overrides_take_precedence(db):
    _, partner = _seed(db)
    firm = firms_repo.get_firm_by_id(db, partner.firm_id)
    ctx_dict = build_context(partner=partner, firm=firm, overrides={"partner.name": "Override"})
    assert ctx_dict["partner.name"] == "Override"


# ---------- Engagement calendar ----------

def test_engagement_list_and_update(db):
    firm, _ = _seed(db)
    rec = eng_repo.insert_engagement(
        db, firm_id=firm.id, partner_id=None,
        due_date="2026-05-15", title="Test entry", track="track-1",
    )
    items = EngagementService.list(_ctx(db), track="track-1")
    assert len(items) == 1 and items[0].title == "Test entry"

    updated = EngagementService.update(
        _ctx(db), rec.ulid,
        EngagementCalendarUpdateInput(status=EngagementStatus.complete),
    )
    assert updated.status == EngagementStatus.complete

    # Audit row recorded
    audit_count = db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE entity_type='engagement_calendar' AND action='plan'"
    ).fetchone()[0]
    assert audit_count == 1


def test_engagement_update_no_fields_raises(db):
    firm, _ = _seed(db)
    rec = eng_repo.insert_engagement(
        db, firm_id=firm.id, partner_id=None,
        due_date="2026-05-15", title="Test",
    )
    with pytest.raises(ValidationError):
        EngagementService.update(_ctx(db), rec.ulid, EngagementCalendarUpdateInput())


# ---------- Templates ----------

def test_template_create_render_round_trip(db):
    _, partner = _seed(db)
    tmpl = TemplatesService.create(_ctx(db), TemplateCreateInput(
        name="cold_intro_v1",
        channel=OutreachChannel.email,
        subject_template="Hello {{partner.name}}",
        body_template="Dear {{partner.name}},\n\nNice to connect.",
        category="cold_intro",
    ))
    rendered = TemplatesService.render(
        _ctx(db), template_ulid=tmpl.ulid, partner_ulid=partner.ulid,
    )
    assert "Test Partner" in rendered["body"]
    assert rendered["subject"] == "Hello Test Partner"
    assert "partner.name" in rendered["used_variables"]


def test_template_name_collision(db):
    TemplatesService.create(_ctx(db), TemplateCreateInput(
        name="dupe", channel=OutreachChannel.email, body_template="body",
    ))
    with pytest.raises(ConflictError):
        TemplatesService.create(_ctx(db), TemplateCreateInput(
            name="dupe", channel=OutreachChannel.email, body_template="body2",
        ))


# ---------- Drafts ----------

def test_create_draft_advances_stage_researched_to_drafted(db):
    _, partner = _seed(db)
    assert partner.outreach_stage == OutreachStage.researched

    OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid,
        channel=OutreachChannel.email,
        subject="hi",
        body="body",
    ))
    refreshed = partners_repo.get_partner_by_id(db, partner.id)
    assert refreshed.outreach_stage == OutreachStage.drafted


def test_update_draft_version_bumps_on_body_change(db):
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid,
        channel=OutreachChannel.email,
        body="version 1 body",
    ))
    assert draft.version == 1
    # Status-only change: no version bump
    OutreachService.update_draft(_ctx(db), draft.ulid, OutreachDraftUpdateInput(status="ready"))
    after_status = outreach_repo.get_draft_by_ulid(db, draft.ulid)
    assert after_status.version == 1
    # Body change: bumps version
    OutreachService.update_draft(_ctx(db), draft.ulid, OutreachDraftUpdateInput(body="v2"))
    after_body = outreach_repo.get_draft_by_ulid(db, draft.ulid)
    assert after_body.version == 2
    versions = outreach_repo.list_draft_versions(db, after_body.id)
    assert len(versions) == 2


def test_update_draft_rejects_status_sent(db):
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid, channel=OutreachChannel.email, body="b",
    ))
    with pytest.raises(ValidationError):
        OutreachService.update_draft(_ctx(db), draft.ulid, OutreachDraftUpdateInput(status="sent"))


# ---------- mark_sent: the CRITICAL atomicity test ----------

def test_mark_sent_happy_path(db):
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid,
        channel=OutreachChannel.email,
        subject="hi",
        body="hello partner",
    ))
    result = OutreachService.mark_sent(_ctx(db), OutreachSendInput(
        draft_ulid=draft.ulid, recipient_handle="alice@example.com",
    ))

    # 1 outreach_message row
    msg_count = db.execute("SELECT COUNT(*) FROM outreach_message").fetchone()[0]
    assert msg_count == 1
    # 1 contact_log row, linked to the message
    contact_count = db.execute(
        "SELECT COUNT(*) FROM contact_log WHERE partner_id = ?", (partner.id,)
    ).fetchone()[0]
    assert contact_count == 1
    # Draft flipped to sent + back-pointer set
    sent_draft = outreach_repo.get_draft_by_ulid(db, draft.ulid)
    assert sent_draft.status.value == "sent"
    assert sent_draft.sent_message_id is not None
    # Partner stage advanced to sent
    refreshed = partners_repo.get_partner_by_id(db, partner.id)
    assert refreshed.outreach_stage == OutreachStage.sent
    # last_contact_date updated
    assert refreshed.last_contact_date == date.today()
    # Audit rows: send + log_contact + (stage advance from drafted→sent)
    audit_actions = [
        r[0] for r in db.execute(
            "SELECT action FROM audit_log ORDER BY id DESC LIMIT 4"
        ).fetchall()
    ]
    assert "send" in audit_actions
    assert "log_contact" in audit_actions
    assert "stage" in audit_actions

    # Response shape
    assert result["stage_advanced"] is True
    assert result["new_stage"] == "sent"


def test_mark_sent_rollback_on_invalid_backdated_sent_at(db):
    """Force an error mid-send (sent_at > 7 days ago) and assert zero side effects."""
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid,
        channel=OutreachChannel.email,
        body="hello",
    ))
    msg_before = db.execute("SELECT COUNT(*) FROM outreach_message").fetchone()[0]
    contact_before = db.execute("SELECT COUNT(*) FROM contact_log").fetchone()[0]
    partner_lcd_before = partners_repo.get_partner_by_id(db, partner.id).last_contact_date

    with pytest.raises(ValidationError):
        OutreachService.mark_sent(_ctx(db), OutreachSendInput(
            draft_ulid=draft.ulid,
            sent_at=datetime.now() - timedelta(days=30),
        ))

    # Zero new rows
    assert db.execute("SELECT COUNT(*) FROM outreach_message").fetchone()[0] == msg_before
    assert db.execute("SELECT COUNT(*) FROM contact_log").fetchone()[0] == contact_before
    # Partner state unchanged
    p = partners_repo.get_partner_by_id(db, partner.id)
    assert p.last_contact_date == partner_lcd_before
    # Draft not flipped
    refreshed = outreach_repo.get_draft_by_ulid(db, draft.ulid)
    assert refreshed.status.value == "draft"


def test_mark_sent_rejects_already_sent_draft(db):
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid, channel=OutreachChannel.email, body="b",
    ))
    OutreachService.mark_sent(_ctx(db), OutreachSendInput(draft_ulid=draft.ulid))
    with pytest.raises(ConflictError):
        OutreachService.mark_sent(_ctx(db), OutreachSendInput(draft_ulid=draft.ulid))


# ---------- Stage explicit set ----------

def test_set_stage(db):
    _, partner = _seed(db)
    OutreachService.set_stage(_ctx(db), partner.ulid, OutreachStage.met)
    refreshed = partners_repo.get_partner_by_id(db, partner.id)
    assert refreshed.outreach_stage == OutreachStage.met
    # Audit row
    n = db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action='stage' AND entity_type='partner'"
    ).fetchone()[0]
    assert n == 1


# ---------- Pipeline ----------

def test_pipeline_returns_all_eight_stages(db):
    _, partner = _seed(db)
    from src.services.pipeline_service import PipelineService
    snap = PipelineService.grouped_by_stage(_ctx(db))
    assert set(snap["stages"].keys()) == {
        "researched", "drafted", "sent", "replied", "met", "ongoing", "paused", "dropped"
    }
    # Seeded partner is in researched
    assert any(c["partner_ulid"] == partner.ulid for c in snap["stages"]["researched"])
    assert snap["counts"]["researched"] == 1


def test_pipeline_filter_by_tier_excludes_others(db):
    firm_spec, _ = _seed(db)
    firm_primary = firms_repo.insert_firm(
        db, name="Big Primary", tier=FirmTier.primary, region="Global"
    )
    partners_repo.insert_partner(db, firm_id=firm_primary.id, name="Other Partner")
    from src.services.pipeline_service import PipelineService
    from src.models import PipelineFilterInput
    snap = PipelineService.grouped_by_stage(
        _ctx(db), PipelineFilterInput(tier=FirmTier.primary)
    )
    names = {c["partner_name"] for stage_list in snap["stages"].values() for c in stage_list}
    assert "Other Partner" in names
    assert "Test Partner" not in names


# ---------- Analytics ----------

def test_analytics_pipeline_funnel_always_eight_keys(db):
    from src.services.analytics_service import AnalyticsService
    funnel = AnalyticsService.pipeline_funnel(_ctx(db))
    assert set(funnel.keys()) == {
        "researched", "drafted", "sent", "replied", "met", "ongoing", "paused", "dropped"
    }


def test_analytics_outreach_volume_after_send(db):
    _, partner = _seed(db)
    draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
        partner_ulid=partner.ulid, channel=OutreachChannel.email, body="hi",
    ))
    OutreachService.mark_sent(_ctx(db), OutreachSendInput(draft_ulid=draft.ulid))
    from src.services.analytics_service import AnalyticsService
    buckets = AnalyticsService.outreach_volume(_ctx(db), granularity="day")
    assert any(b["count"] >= 1 for b in buckets)


def test_analytics_response_rate(db):
    """Use two different channels to avoid the (partner,date,channel) UNIQUE collision
    that's intentional on contact_log."""
    _, partner = _seed(db)
    channels = [OutreachChannel.email, OutreachChannel.linkedin]
    for ch in channels:
        draft = OutreachService.create_draft(_ctx(db), OutreachDraftCreateInput(
            partner_ulid=partner.ulid, channel=ch, body=f"hi {ch.value}",
        ))
        OutreachService.mark_sent(_ctx(db), OutreachSendInput(draft_ulid=draft.ulid))
    from src.models import ContactChannel, InitiatedBy
    contacts_repo.insert_contact(
        db, partner_id=partner.id, contact_date=date.today(),
        channel=ContactChannel.call, initiated_by=InitiatedBy.them, summary="they replied",
    )
    from src.services.analytics_service import AnalyticsService
    rr = AnalyticsService.response_rate(_ctx(db))
    assert rr["sent"] == 2
    assert rr["incoming"] == 1
    assert rr["rate"] == 0.5
