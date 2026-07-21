"""Explainable, deterministic Today / next-best-action service.

Executive and board data are queried independently and combined only in memory.
No generated recommendation is written to search, notes, or the event outbox.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..models import AuditAction
from ..repository import today_feedback as feedback_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .board_tasks_service import BoardTasksService
from .engagement_service import EngagementService
from .exceptions import ValidationError


class TodayService:
    MAX_ACTIONS = 5

    @staticmethod
    def _urgency(due: str | date | None, today: date) -> tuple[int, list[str]]:
        if due is None:
            return 5, ["No follow-up date recorded"]
        value = date.fromisoformat(str(due))
        delta = (value - today).days
        if delta < 0:
            days = -delta
            return 40 + min(days, 30), [f"Overdue by {days} day{'s' if days != 1 else ''}"]
        if delta == 0:
            return 35, ["Due today"]
        if delta <= 3:
            return 28 - delta, [f"Due in {delta} day{'s' if delta != 1 else ''}"]
        if delta <= 14:
            return 16, [f"Due within {delta} days"]
        return 0, [f"Due in {delta} days"]

    @staticmethod
    def _item(*, source_key: str, workstream: str, action_type: str,
              entity_type: str, entity_ulid: str, title: str, href: str,
              due_date: Any, base: int, reasons: list[str], today: date,
              context: str | None = None) -> dict[str, Any]:
        urgency, urgency_reasons = TodayService._urgency(due_date, today)
        return {
            "source_key": source_key,
            "workstream": workstream,
            "action_type": action_type,
            "entity_type": entity_type,
            "entity_ulid": entity_ulid,
            "title": title,
            "context": context,
            "href": href,
            "due_date": str(due_date) if due_date else None,
            "score": base + urgency,
            "reasons": reasons + urgency_reasons,
            "operations": TodayService._operations(action_type),
        }

    @staticmethod
    def _operations(action_type: str) -> list[str]:
        """Allowed UI operations. Hard obligations can never be dismissed."""
        if action_type in {"planned_task", "board_task"}:
            return ["open", "complete", "snooze"]
        if action_type == "relationship_touch":
            return ["open", "snooze", "dismiss"]
        return ["open", "snooze"]

    @staticmethod
    def list_actions(ctx: ServiceContext, *, on_date: date | None = None) -> dict[str, Any]:
        assert_owner(ctx, operation="read Today recommendations")
        today = on_date or date.today()
        cutoff = today + timedelta(days=14)
        items: list[dict[str, Any]] = []

        # Executive sources: kept entirely within executive tables.
        rows = ctx.conn.execute(
            "SELECT p.ulid, p.name, p.next_touch_date, f.name firm_name, f.tier "
            "FROM partners p JOIN firms f ON f.id = p.firm_id "
            "WHERE p.deleted_at IS NULL AND f.deleted_at IS NULL "
            "AND p.next_touch_date IS NOT NULL AND p.next_touch_date <= ?",
            (cutoff,),
        ).fetchall()
        for r in rows:
            tier_bonus = 20 if r["tier"] == "primary" else 10 if r["tier"] == "specialist" else 4
            items.append(TodayService._item(
                source_key=f"executive:partner:{r['ulid']}:touch", workstream="executive",
                action_type="relationship_touch", entity_type="partner", entity_ulid=r["ulid"],
                title=f"Reconnect with {r['name']}", context=r["firm_name"],
                href=f"/partners/{r['ulid']}", due_date=r["next_touch_date"],
                base=20 + tier_bonus, reasons=[f"{str(r['tier']).replace('_', ' ').title()} search-firm relationship"], today=today,
            ))

        rows = ctx.conn.execute(
            "SELECT e.ulid, e.role_title, e.stage, e.interest, e.next_step, e.next_step_date, o.name org_name "
            "FROM engagements e JOIN organisations o ON o.id = e.org_id "
            "WHERE e.deleted_at IS NULL AND o.deleted_at IS NULL AND e.stage <> 'closed' "
            "AND e.next_step IS NOT NULL AND (e.next_step_date IS NULL OR e.next_step_date <= ?)",
            (cutoff,),
        ).fetchall()
        for r in rows:
            stage_bonus = {"formal": 12, "final": 20, "offer": 25, "decision": 24}.get(r["stage"], 5)
            interest_bonus = 10 if r["interest"] == "preferred" else 6 if r["interest"] == "active" else 0
            items.append(TodayService._item(
                source_key=f"executive:engagement:{r['ulid']}:next", workstream="executive",
                action_type="opportunity_next_step", entity_type="engagement", entity_ulid=r["ulid"],
                title=r["next_step"], context=f"{r['org_name']} · {r['role_title']}",
                href=f"/engagements/{r['ulid']}", due_date=r["next_step_date"],
                base=30 + stage_bonus + interest_bonus,
                reasons=[f"Live {r['stage']} executive opportunity"], today=today,
            ))

        for r in ctx.conn.execute(
            "SELECT ulid, subject, recipient_hint, created_at FROM messages "
            "WHERE status = 'proposed' ORDER BY created_at ASC"
        ).fetchall():
            items.append({
                "source_key": f"executive:message:{r['ulid']}:approval", "workstream": "executive",
                "action_type": "message_approval", "entity_type": "message", "entity_ulid": r["ulid"],
                "title": f"Review draft: {r['subject'] or 'Untitled message'}",
                "context": r["recipient_hint"], "href": "/messages", "due_date": None,
                "score": 50, "reasons": ["Awaiting your approval", "No message is sent automatically"],
                "operations": TodayService._operations("message_approval"),
            })

        for r in ctx.conn.execute(
            "SELECT ulid, title, due_date, track FROM engagement_calendar "
            "WHERE status <> 'complete' AND due_date <= ?", (cutoff,)
        ).fetchall():
            items.append(TodayService._item(
                source_key=f"executive:calendar:{r['ulid']}:task", workstream="executive",
                action_type="planned_task", entity_type="engagement_calendar", entity_ulid=r["ulid"],
                title=r["title"], context=r["track"], href="/engagement", due_date=r["due_date"],
                base=18, reasons=["Planned executive-search activity"], today=today,
            ))

        # Board sources: independent queries; combined with executive items only here.
        for r in ctx.conn.execute(
            "SELECT ulid, title, due_date, linked_entity_type FROM board_task "
            "WHERE status = 'open' AND (due_date IS NULL OR due_date <= ?)", (cutoff,)
        ).fetchall():
            items.append(TodayService._item(
                source_key=f"board:task:{r['ulid']}", workstream="board", action_type="board_task",
                entity_type="board_task", entity_ulid=r["ulid"], title=r["title"],
                context=r["linked_entity_type"], href="/board/tasks", due_date=r["due_date"],
                base=24, reasons=["Open Board / NED task"], today=today,
            ))

        for r in ctx.conn.execute(
            "SELECT ulid, next_action, due_date, linked_entity_type FROM board_interaction "
            "WHERE next_action IS NOT NULL AND due_date IS NOT NULL AND due_date <= ?", (cutoff,)
        ).fetchall():
            items.append(TodayService._item(
                source_key=f"board:interaction:{r['ulid']}:followup", workstream="board",
                action_type="board_follow_up", entity_type="board_interaction", entity_ulid=r["ulid"],
                title=r["next_action"], context=r["linked_entity_type"], href="/board/outreach-due",
                due_date=r["due_date"], base=28, reasons=["Committed Board / NED follow-up"], today=today,
            ))

        for r in ctx.conn.execute(
            "SELECT ulid, organisation, stage, interest, next_step, next_step_due_date "
            "FROM board_opportunity WHERE deleted_at IS NULL AND outcome IS NULL "
            "AND next_step IS NOT NULL AND (next_step_due_date IS NULL OR next_step_due_date <= ?)",
            (cutoff,),
        ).fetchall():
            stage_bonus = {"formal_process": 12, "final_nomco": 20, "offer": 25, "decision": 24}.get(r["stage"], 5)
            interest_bonus = 10 if r["interest"] == "preferred" else 6 if r["interest"] == "active" else 0
            items.append(TodayService._item(
                source_key=f"board:opportunity:{r['ulid']}:next", workstream="board",
                action_type="board_opportunity_next_step", entity_type="board_opportunity", entity_ulid=r["ulid"],
                title=r["next_step"], context=r["organisation"], href=f"/board/opportunities/{r['ulid']}",
                due_date=r["next_step_due_date"], base=32 + stage_bonus + interest_bonus,
                reasons=[f"Live {str(r['stage']).replace('_', ' ')} board opportunity"], today=today,
            ))

        feedback = feedback_repo.list_feedback(ctx.conn)
        visible: list[dict[str, Any]] = []
        for item in items:
            override = feedback.get(item["source_key"])
            if override:
                disposition = override["disposition"]
                if disposition in {"completed", "dismissed"}:
                    continue
                if disposition == "snoozed" and date.fromisoformat(override["snoozed_until"]) > today:
                    continue
            visible.append(item)
        visible.sort(key=lambda x: (-x["score"], x["due_date"] or "9999-12-31", x["source_key"]))
        counts = {
            "executive": sum(i["workstream"] == "executive" for i in visible),
            "board": sum(i["workstream"] == "board" for i in visible),
        }
        return {
            "date": today.isoformat(),
            "actions": visible[: TodayService.MAX_ACTIONS],
            "available": len(visible),
            "counts": counts,
            "overview": TodayService._overview(ctx, today=today, all_items=items),
        }

    @staticmethod
    def _overview(ctx: ServiceContext, *, today: date, all_items: list[dict[str, Any]]) -> dict[str, Any]:
        """Compact combined read model; every cross-domain row remains labelled."""
        opportunities: list[dict[str, Any]] = []
        for r in ctx.conn.execute(
            "SELECT e.ulid, e.role_title title, e.stage, e.next_step_date due_date, o.name organisation "
            "FROM engagements e JOIN organisations o ON o.id=e.org_id "
            "WHERE e.deleted_at IS NULL AND o.deleted_at IS NULL AND e.stage <> 'closed' "
            "ORDER BY CASE e.stage WHEN 'offer' THEN 1 WHEN 'final' THEN 2 WHEN 'formal' THEN 3 ELSE 4 END, e.updated_at DESC LIMIT 4"
        ).fetchall():
            opportunities.append({"workstream": "executive", "ulid": r["ulid"], "title": r["title"], "organisation": r["organisation"], "stage": r["stage"], "due_date": str(r["due_date"]) if r["due_date"] else None, "href": f"/engagements/{r['ulid']}"})
        for r in ctx.conn.execute(
            "SELECT ulid, organisation, role title, stage, next_step_due_date due_date FROM board_opportunity "
            "WHERE deleted_at IS NULL AND outcome IS NULL "
            "ORDER BY CASE stage WHEN 'offer' THEN 1 WHEN 'final_nomco' THEN 2 WHEN 'formal_process' THEN 3 ELSE 4 END, updated_at DESC LIMIT 4"
        ).fetchall():
            opportunities.append({"workstream": "board", "ulid": r["ulid"], "title": str(r["title"] or "Board appointment").replace("_", " ").title(), "organisation": r["organisation"], "stage": r["stage"], "due_date": str(r["due_date"]) if r["due_date"] else None, "href": f"/board/opportunities/{r['ulid']}"})

        deadlines = [
            {k: item[k] for k in ("source_key", "workstream", "title", "due_date", "href")}
            for item in sorted(
                (i for i in all_items if i["due_date"]),
                key=lambda i: (i["due_date"], i["source_key"]),
            )[:6]
        ]

        cooling: list[dict[str, Any]] = []
        threshold = today - timedelta(days=90)
        for r in ctx.conn.execute(
            "SELECT p.ulid, p.name, p.last_contact_date, f.name firm_name FROM partners p "
            "JOIN firms f ON f.id=p.firm_id WHERE p.deleted_at IS NULL AND f.deleted_at IS NULL "
            "AND (p.last_contact_date IS NULL OR p.last_contact_date <= ?) ORDER BY p.last_contact_date LIMIT 4",
            (threshold,),
        ).fetchall():
            cooling.append({"workstream": "executive", "ulid": r["ulid"], "name": r["name"], "organisation": r["firm_name"], "last_contact_date": str(r["last_contact_date"]) if r["last_contact_date"] else None, "href": f"/partners/{r['ulid']}"})
        for r in ctx.conn.execute(
            "SELECT c.ulid, c.name, c.last_contact_date, f.name firm_name FROM board_contact c "
            "LEFT JOIN board_firm f ON f.id=c.firm_id WHERE c.deleted_at IS NULL "
            "AND (c.last_contact_date IS NULL OR c.last_contact_date <= ?) ORDER BY c.last_contact_date LIMIT 4",
            (threshold,),
        ).fetchall():
            cooling.append({"workstream": "board", "ulid": r["ulid"], "name": r["name"], "organisation": r["firm_name"], "last_contact_date": str(r["last_contact_date"]) if r["last_contact_date"] else None, "href": "/board/contacts"})

        return {
            "live_opportunities": opportunities[:6],
            "deadlines": deadlines,
            "cooling_contacts": cooling[:6],
            "metrics": {
                "live_opportunities": len(opportunities),
                "overdue_actions": sum(bool(i["due_date"] and i["due_date"] < today.isoformat()) for i in all_items),
                "cooling_contacts": len(cooling),
            },
        }

    @staticmethod
    def record_feedback(ctx: ServiceContext, *, source_key: str, workstream: str,
                        disposition: str, snoozed_until: date | None = None,
                        reason: str | None = None) -> dict[str, Any]:
        assert_owner(ctx, operation="change Today recommendation")
        if workstream not in {"executive", "board"}:
            raise ValidationError("workstream must be executive or board")
        if disposition not in {"completed", "snoozed", "dismissed"}:
            raise ValidationError("disposition must be completed, snoozed or dismissed")
        if disposition == "snoozed" and (snoozed_until is None or snoozed_until <= date.today()):
            raise ValidationError("snoozed_until must be a future date")
        if disposition != "snoozed":
            snoozed_until = None
        if disposition == "completed":
            # Completion resolves the canonical source record; it is never a
            # cosmetic recommendation override.
            parts = source_key.split(":")
            if len(parts) == 3 and parts[:2] == ["board", "task"]:
                BoardTasksService.mark_done(ctx, parts[2])
            elif len(parts) == 4 and parts[:2] == ["executive", "calendar"] and parts[3] == "task":
                EngagementService.mark_complete(ctx, parts[2])
            else:
                raise ValidationError("this recommendation must be completed from its source workflow")
            return {"source_key": source_key, "workstream": workstream, "disposition": "completed"}
        if disposition == "dismissed" and not source_key.startswith("executive:partner:"):
            raise ValidationError("only generated relationship suggestions may be dismissed")
        with transaction(ctx.conn):
            row = feedback_repo.upsert_feedback(
                ctx.conn, source_key=source_key, workstream=workstream,
                disposition=disposition, snoozed_until=snoozed_until, reason=reason,
            )
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="today_feedback",
                entity_id=row["id"], entity_ulid=row["ulid"], after=row,
            )
        return row
