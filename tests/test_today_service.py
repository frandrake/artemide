from datetime import date, timedelta

import pytest

from src.services import ServiceContext
from src.services.exceptions import ValidationError
from src.services.today_service import TodayService


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="cli")


def _insert_firm_partner(db, *, tier="primary", due=None):
    firm_ulid = "01HFIRM000000000000000000"
    partner_ulid = "01HPARTNER00000000000000"
    cur = db.execute(
        "INSERT INTO firms (ulid, name, tier, relationship_state) VALUES (?, ?, ?, ?)",
        (firm_ulid, "Example Search", tier, "warm"),
    )
    db.execute(
        "INSERT INTO partners (ulid, firm_id, name, relationship_state, next_touch_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (partner_ulid, cur.lastrowid, "Alex Partner", "warm", due),
    )
    db.commit()
    return partner_ulid


def _insert_board_task(db, *, due=None):
    ulid = "01HBOARDTASK0000000000000"
    db.execute(
        "INSERT INTO board_task (ulid, title, due_date, status) VALUES (?, ?, ?, 'open')",
        (ulid, "Call the chair", due),
    )
    db.commit()
    return ulid


def test_today_combines_but_labels_workstreams_and_caps_at_five(ctx, db):
    today = date(2026, 7, 21)
    _insert_firm_partner(db, due=today - timedelta(days=2))
    _insert_board_task(db, due=today)

    result = TodayService.list_actions(ctx, on_date=today)

    assert len(result["actions"]) == 2
    assert {a["workstream"] for a in result["actions"]} == {"executive", "board"}
    assert result["actions"][0]["score"] >= result["actions"][1]["score"]
    assert all(a["reasons"] for a in result["actions"])
    assert all(a["operations"] for a in result["actions"])
    assert all(a["source_key"].startswith(("executive:", "board:")) for a in result["actions"])
    assert len(result["actions"]) <= 5


def test_today_snooze_and_dismiss_hide_recommendation(ctx, db):
    today = date.today()
    partner_ulid = _insert_firm_partner(db, due=today)
    source_key = f"executive:partner:{partner_ulid}:touch"

    TodayService.record_feedback(
        ctx,
        source_key=source_key,
        workstream="executive",
        disposition="snoozed",
        snoozed_until=today + timedelta(days=3),
    )
    assert TodayService.list_actions(ctx, on_date=today)["actions"] == []
    assert TodayService.list_actions(ctx, on_date=today + timedelta(days=3))["actions"]

    TodayService.record_feedback(
        ctx, source_key=source_key, workstream="executive", disposition="dismissed"
    )
    assert TodayService.list_actions(ctx, on_date=today + timedelta(days=3))["actions"] == []
    audit = db.execute(
        "SELECT action, entity_type FROM audit_log WHERE entity_type = 'today_feedback'"
    ).fetchall()
    assert len(audit) == 2
    assert all(row["action"] == "update" for row in audit)


def test_today_rejects_invalid_feedback(ctx):
    with pytest.raises(ValidationError):
        TodayService.record_feedback(
            ctx,
            source_key="executive:partner:test:touch",
            workstream="executive",
            disposition="snoozed",
            snoozed_until=date.today(),
        )


def test_today_completion_updates_canonical_board_task(ctx, db):
    ulid = _insert_board_task(db, due=date.today())
    TodayService.record_feedback(
        ctx, source_key=f"board:task:{ulid}", workstream="board", disposition="completed"
    )
    assert db.execute("SELECT status FROM board_task WHERE ulid = ?", (ulid,)).fetchone()["status"] == "done"
    assert TodayService.list_actions(ctx)["actions"] == []


def test_today_cannot_cosmetically_complete_or_dismiss_hard_action(ctx, db):
    ulid = _insert_board_task(db, due=date.today())
    with pytest.raises(ValidationError):
        TodayService.record_feedback(
            ctx, source_key=f"board:task:{ulid}", workstream="board", disposition="dismissed"
        )
    with pytest.raises(ValidationError):
        TodayService.record_feedback(
            ctx, source_key="executive:message:test:approval", workstream="executive", disposition="completed"
        )
