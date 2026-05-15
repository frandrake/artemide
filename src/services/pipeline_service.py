"""Pipeline service: partners grouped by outreach_stage for the Kanban view."""
from __future__ import annotations

from typing import Any

from ..models import OutreachStage, PipelineFilterInput
from . import ServiceContext


_STAGES = [s.value for s in OutreachStage]


def _row_to_card(row) -> dict[str, Any]:
    return {
        "partner_ulid": row["partner_ulid"],
        "partner_name": row["partner_name"],
        "firm_ulid": row["firm_ulid"],
        "firm_name": row["firm_name"],
        "firm_tier": row["firm_tier"],
        "strategic_relevance": row["strategic_relevance"],
        "ned_gateway": bool(row["ned_gateway"]),
        "last_contact_date": row["last_contact_date"],
        "next_touch_date": row["next_touch_date"],
        "open_draft_ulid": row["open_draft_ulid"],
        "sent_count": int(row["sent_count"] or 0),
        "outreach_stage": row["outreach_stage"],
    }


class PipelineService:

    @staticmethod
    def grouped_by_stage(
        ctx: ServiceContext, filters: PipelineFilterInput | None = None
    ) -> dict[str, Any]:
        filters = filters or PipelineFilterInput()
        clauses = ["p.deleted_at IS NULL", "f.deleted_at IS NULL"]
        params: list[Any] = []
        if filters.tier is not None:
            clauses.append("f.tier = ?")
            params.append(filters.tier.value)
        if filters.strategic_relevance is not None:
            clauses.append("p.strategic_relevance = ?")
            params.append(filters.strategic_relevance)
        if filters.ned_gateway is True:
            clauses.append("p.ned_gateway = 1")
        elif filters.ned_gateway is False:
            clauses.append("p.ned_gateway = 0")
        if filters.track is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM engagement_calendar ec "
                "WHERE ec.partner_id = p.id AND ec.track = ?)"
            )
            params.append(filters.track)

        sql = (
            "SELECT "
            "  p.ulid AS partner_ulid, "
            "  p.name AS partner_name, "
            "  p.outreach_stage AS outreach_stage, "
            "  p.strategic_relevance AS strategic_relevance, "
            "  p.ned_gateway AS ned_gateway, "
            "  p.last_contact_date AS last_contact_date, "
            "  p.next_touch_date AS next_touch_date, "
            "  f.ulid AS firm_ulid, "
            "  f.name AS firm_name, "
            "  f.tier AS firm_tier, "
            "  (SELECT od.ulid FROM outreach_draft od "
            "     WHERE od.partner_id = p.id AND od.status IN ('draft','ready') "
            "     ORDER BY od.updated_at DESC LIMIT 1) AS open_draft_ulid, "
            "  (SELECT COUNT(*) FROM outreach_message om WHERE om.partner_id = p.id) AS sent_count "
            "FROM partners p "
            "JOIN firms f ON f.id = p.firm_id "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY p.outreach_stage, p.name"
        )
        rows = ctx.conn.execute(sql, params).fetchall()

        stages: dict[str, list[dict[str, Any]]] = {s: [] for s in _STAGES}
        for row in rows:
            stage = row["outreach_stage"]
            if stage in stages:
                stages[stage].append(_row_to_card(row))
        counts = {s: len(v) for s, v in stages.items()}
        return {"stages": stages, "counts": counts}
