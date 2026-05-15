"""Analytics service — outreach volume, response rate, reciprocity, plan execution, funnel."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal

from ..models import InitiatedBy, OutreachStage
from ..repository import contacts as contacts_repo
from ..repository import engagement_calendar as eng_repo
from ..repository import outreach as outreach_repo
from . import ServiceContext


Granularity = Literal["day", "week", "month"]


def _default_window(days: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=days), today


def _bucket(d: str, granularity: Granularity) -> str:
    dt = date.fromisoformat(d)
    if granularity == "day":
        return dt.isoformat()
    if granularity == "week":
        # ISO week: Monday of that week
        monday = dt - timedelta(days=dt.weekday())
        return monday.isoformat()
    if granularity == "month":
        return f"{dt.year:04d}-{dt.month:02d}-01"
    return dt.isoformat()


class AnalyticsService:

    @staticmethod
    def outreach_volume(
        ctx: ServiceContext,
        *,
        granularity: Granularity = "week",
        since: date | None = None,
        until: date | None = None,
    ) -> list[dict[str, Any]]:
        if since is None or until is None:
            since, until = _default_window(90)
        # Combine outreach_message + contact_log where initiated_by=me
        msg_per_day = outreach_repo.count_messages_by_day(ctx.conn, since=since, until=until)
        contacts_per_day = contacts_repo.count_contacts_by_day(
            ctx.conn, initiated_by=InitiatedBy.me, since=since, until=until
        )
        # Bucket
        buckets: dict[str, int] = {}
        for d, n in msg_per_day:
            buckets[_bucket(d, granularity)] = buckets.get(_bucket(d, granularity), 0) + n
        # Avoid double-counting: outreach_message always creates a contact_log row.
        # The contact_log query is here only for completeness — manually-logged contacts
        # (initiated_by=me but no draft) would otherwise be missed.
        # Strategy: count contacts_per_day as the canonical figure; messages are a subset.
        buckets = {}
        for d, n in contacts_per_day:
            buckets[_bucket(d, granularity)] = buckets.get(_bucket(d, granularity), 0) + n
        return [{"bucket": k, "count": v} for k, v in sorted(buckets.items())]

    @staticmethod
    def response_rate(
        ctx: ServiceContext,
        *,
        since: date | None = None,
        until: date | None = None,
    ) -> dict[str, Any]:
        if since is None or until is None:
            since, until = _default_window(30)
        sent = contacts_repo.count_contacts_in_window(
            ctx.conn, initiated_by=InitiatedBy.me, since=since, until=until
        )
        incoming = contacts_repo.count_contacts_in_window(
            ctx.conn, initiated_by=InitiatedBy.them, since=since, until=until
        )
        rate = (incoming / sent) if sent > 0 else 0.0
        return {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "sent": sent,
            "incoming": incoming,
            "rate": round(rate, 4),
        }

    @staticmethod
    def reciprocity_per_partner(ctx: ServiceContext) -> list[dict[str, Any]]:
        rows = ctx.conn.execute(
            "SELECT "
            "  p.ulid AS partner_ulid, p.name AS partner_name, "
            "  f.name AS firm_name, "
            "  SUM(CASE WHEN cl.value_given IS NOT NULL AND cl.value_given <> '' THEN 1 ELSE 0 END) AS given, "
            "  SUM(CASE WHEN cl.value_received IS NOT NULL AND cl.value_received <> '' THEN 1 ELSE 0 END) AS received "
            "FROM partners p "
            "JOIN firms f ON f.id = p.firm_id "
            "LEFT JOIN contact_log cl ON cl.partner_id = p.id "
            "WHERE p.deleted_at IS NULL AND f.deleted_at IS NULL "
            "GROUP BY p.id "
            "ORDER BY ABS((SUM(CASE WHEN cl.value_given IS NOT NULL AND cl.value_given <> '' THEN 1 ELSE 0 END) - "
            "             SUM(CASE WHEN cl.value_received IS NOT NULL AND cl.value_received <> '' THEN 1 ELSE 0 END))) DESC, "
            "         p.name"
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            given = int(r["given"] or 0)
            received = int(r["received"] or 0)
            out.append({
                "partner_ulid": r["partner_ulid"],
                "partner_name": r["partner_name"],
                "firm_name": r["firm_name"],
                "given": given,
                "received": received,
                "balance": given - received,
            })
        return out

    @staticmethod
    def plan_execution(
        ctx: ServiceContext,
        *,
        since: date | None = None,
        until: date | None = None,
    ) -> dict[str, Any]:
        if since is None or until is None:
            since = date.today() - timedelta(days=30)
            until = date.today() + timedelta(days=30)
        counts = eng_repo.count_engagements_by_status(
            ctx.conn, due_after=since, due_before=until
        )
        total = sum(counts.values())
        complete = counts.get("complete", 0)
        return {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "complete": complete,
            "total": total,
            "percent": round(complete / total, 4) if total > 0 else 0.0,
            "by_status": counts,
        }

    @staticmethod
    def pipeline_funnel(ctx: ServiceContext) -> dict[str, int]:
        rows = ctx.conn.execute(
            "SELECT outreach_stage, COUNT(*) AS n FROM partners "
            "WHERE deleted_at IS NULL GROUP BY outreach_stage"
        ).fetchall()
        # Always return all 8 stages
        funnel: dict[str, int] = {s.value: 0 for s in OutreachStage}
        for r in rows:
            stage = r["outreach_stage"]
            if stage in funnel:
                funnel[stage] = int(r["n"])
        return funnel
