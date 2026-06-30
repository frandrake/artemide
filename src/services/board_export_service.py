"""Board export service. Per-domain markdown ledger and per-entity CSV.

Owner-only; a separate service + router from the exec export so the two corpora
never intermix. The markdown form round-trips with board_import_service.
"""
from __future__ import annotations

import csv
import io

from ..repository import board_contacts as contacts_repo
from ..repository import board_evaluations as evaluations_repo
from ..repository import board_firms as firms_repo
from ..repository import board_opportunities as opportunities_repo
from . import ServiceContext, assert_owner


def _kv(label: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return f"  - **{label}:** {value}"


class BoardExportService:

    @staticmethod
    def export_to_markdown(ctx: ServiceContext) -> str:
        assert_owner(ctx, operation="export board ledger")
        lines: list[str] = ["# Artemide Board Ledger", ""]

        firms = firms_repo.list_firms(ctx.conn)
        by_tier: dict[int | None, list] = {}
        for f in firms:
            by_tier.setdefault(f.tier, []).append(f)
        for tier in sorted((t for t in by_tier if t is not None)) + ([None] if None in by_tier else []):
            tier_label = str(tier) if tier is not None else "untiered"
            lines.append(f"## Tier: {tier_label}")
            lines.append("")
            for firm in by_tier[tier]:
                lines.append(f"### Firm: {firm.name}")
                meta = [
                    _kv("Type", firm.firm_type.value if firm.firm_type else None),
                    _kv("Geography", ", ".join(g.value for g in firm.geography) if firm.geography else None),
                    _kv("Sectors", firm.sectors_level),
                    _kv("AI-hook", firm.ai_on_boards_hook),
                    _kv("Status", firm.status.value),
                    _kv("Next-action", firm.next_action),
                    _kv("Source-url", firm.source_url),
                    _kv("Notes", firm.notes),
                ]
                lines.extend(m for m in meta if m)
                lines.append("")
                for c in contacts_repo.list_contacts(ctx.conn, firm_id=firm.id):
                    lines.append(f"#### Contact: {c.name}")
                    cmeta = [
                        _kv("Role", c.role_title),
                        _kv("Practice", c.practice.value if c.practice else None),
                        _kv("Email", c.email),
                        _kv("LinkedIn", c.linkedin),
                        _kv("Mutual", c.mutual_connections),
                        _kv("Relationship", c.relationship.value),
                        _kv("Last-contact", c.last_contact_date.isoformat() if c.last_contact_date else None),
                        _kv("Source-url", c.source_url),
                        _kv("Notes", c.notes),
                    ]
                    lines.extend(m for m in cmeta if m)
                    lines.append("")
                lines.append("")

        opportunities = opportunities_repo.list_opportunities(ctx.conn, sort="date_surfaced")
        if opportunities:
            lines.append("## Opportunities")
            lines.append("")
            for o in opportunities:
                lines.append(f"### Opportunity: {o.organisation}")
                ometa = [
                    _kv("Board-type", o.board_type.value if o.board_type else None),
                    _kv("Role", o.role.value if o.role else None),
                    _kv("Stage", o.stage.value),
                    _kv("Conflict-cleared", o.conflict_cleared.value),
                    _kv("Interest", o.interest.value),
                    _kv("Weighted-total", str(o.eval_weighted_total) if o.eval_weighted_total is not None else None),
                    _kv("Verdict", o.eval_verdict),
                    _kv("Next-step", o.next_step),
                    _kv("Notes", o.notes),
                ]
                lines.extend(m for m in ometa if m)
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def export_to_csv(ctx: ServiceContext, entity_type: str) -> str:
        assert_owner(ctx, operation="export board csv")
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        if entity_type == "board_firm":
            writer.writerow(["ulid", "name", "firm_type", "geography", "tier", "status",
                             "sectors_level", "ai_on_boards_hook", "next_action", "source_url", "notes"])
            for f in firms_repo.list_firms(ctx.conn):
                writer.writerow([
                    f.ulid, f.name, f.firm_type.value if f.firm_type else "",
                    "|".join(g.value for g in f.geography), f.tier or "", f.status.value,
                    f.sectors_level or "", f.ai_on_boards_hook or "", f.next_action or "",
                    f.source_url or "", f.notes or "",
                ])
        elif entity_type == "board_contact":
            writer.writerow(["ulid", "firm_name", "name", "role_title", "practice", "email",
                             "linkedin", "relationship", "last_contact_date", "mutual_connections", "notes"])
            firm_map = {f.id: f for f in firms_repo.list_firms(ctx.conn, include_deleted=True)}
            for c in contacts_repo.list_contacts(ctx.conn):
                firm = firm_map.get(c.firm_id) if c.firm_id is not None else None
                writer.writerow([
                    c.ulid, firm.name if firm else "", c.name, c.role_title or "",
                    c.practice.value if c.practice else "", c.email or "", c.linkedin or "",
                    c.relationship.value,
                    c.last_contact_date.isoformat() if c.last_contact_date else "",
                    c.mutual_connections or "", c.notes or "",
                ])
        elif entity_type == "board_opportunity":
            writer.writerow(["ulid", "organisation", "board_type", "role", "stage",
                             "conflict_cleared", "interest", "eval_weighted_total", "eval_verdict",
                             "date_surfaced", "next_step"])
            for o in opportunities_repo.list_opportunities(ctx.conn):
                writer.writerow([
                    o.ulid, o.organisation, o.board_type.value if o.board_type else "",
                    o.role.value if o.role else "", o.stage.value, o.conflict_cleared.value,
                    o.interest.value,
                    o.eval_weighted_total if o.eval_weighted_total is not None else "",
                    o.eval_verdict or "",
                    o.date_surfaced.isoformat() if o.date_surfaced else "", o.next_step or "",
                ])
        elif entity_type == "board_evaluation":
            writer.writerow(["opportunity_ulid", "organisation", "chair_board_quality",
                             "mandate_contribution_fit", "governance_health_risk", "time_conflict_cost",
                             "brand_portfolio_value", "terms", "weighted_total", "verdict",
                             "hard_disqualifiers"])
            opps = opportunities_repo.list_opportunities(ctx.conn)
            eval_map = evaluations_repo.get_by_opportunity_ids(ctx.conn, [o.id for o in opps])
            for o in opps:
                ev = eval_map.get(o.id)
                if ev is None:
                    continue
                writer.writerow([
                    o.ulid, o.organisation, ev.score_chair_board_quality or "",
                    ev.score_mandate_contribution_fit or "", ev.score_governance_health_risk or "",
                    ev.score_time_conflict_cost or "", ev.score_brand_portfolio_value or "",
                    ev.score_terms or "", ev.weighted_total if ev.weighted_total is not None else "",
                    ev.verdict.value if ev.verdict else "",
                    "|".join(ev.hard_disqualifiers),
                ])
        else:
            raise ValueError(f"unsupported entity_type for board CSV export: {entity_type}")
        return buf.getvalue()
