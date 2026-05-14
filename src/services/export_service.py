"""Export service. Markdown ledger and per-entity CSV."""
from __future__ import annotations

import csv
import io
from typing import Iterable

from ..models import ContactChannel, FirmTier, InitiatedBy
from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from . import ServiceContext


def _format_kv(label: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return f"  - **{label}:** {value}"


class ExportService:

    @staticmethod
    def export_to_markdown(ctx: ServiceContext) -> str:
        lines: list[str] = ["# Artemide Ledger", ""]
        for tier in (FirmTier.primary, FirmTier.specialist, FirmTier.ned):
            firms = firms_repo.list_firms(ctx.conn, tier=tier)
            if not firms:
                continue
            lines.append(f"## Tier: {tier.value}")
            lines.append("")
            for firm in firms:
                lines.append(f"### Firm: {firm.name}")
                meta = [
                    _format_kv("Region", firm.region),
                    _format_kv("State", firm.relationship_state.value),
                    _format_kv("Focus", firm.primary_focus),
                    _format_kv("Notes", firm.notes_summary),
                ]
                lines.extend(m for m in meta if m)
                lines.append("")
                partners = partners_repo.list_partners_by_firm(ctx.conn, firm.id)
                for p in partners:
                    lines.append(f"#### Partner: {p.name}")
                    pmeta = [
                        _format_kv("Title", p.title),
                        _format_kv("Practice", p.practice),
                        _format_kv("Seniority", p.seniority),
                        _format_kv("Email", p.email),
                        _format_kv("LinkedIn", p.linkedin_url),
                        _format_kv("State", p.relationship_state.value),
                        _format_kv("Next-touch-date",
                                   p.next_touch_date.isoformat() if p.next_touch_date else None),
                        _format_kv("Next-touch-topic", p.next_touch_topic),
                        _format_kv("Notes", p.notes_summary),
                    ]
                    lines.extend(m for m in pmeta if m)
                    contacts = contacts_repo.list_contacts_by_partner(ctx.conn, p.id)
                    if contacts:
                        lines.append("")
                        lines.append("##### Contacts")
                        for c in sorted(contacts, key=lambda x: x.contact_date):
                            line = (
                                f"- {c.contact_date.isoformat()} | {c.channel.value} | "
                                f"{c.initiated_by.value}"
                            )
                            lines.append(line)
                            cdetail = [
                                _format_kv("Summary", c.summary),
                                _format_kv("Value-given", c.value_given),
                                _format_kv("Value-received", c.value_received),
                                _format_kv("Follow-up", c.follow_up),
                            ]
                            lines.extend(d for d in cdetail if d)
                    lines.append("")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def export_to_csv(ctx: ServiceContext, entity_type: str) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        if entity_type == "firm":
            writer.writerow(["ulid", "name", "tier", "region", "relationship_state",
                             "primary_focus", "notes_summary"])
            for f in firms_repo.list_firms(ctx.conn):
                writer.writerow([f.ulid, f.name, f.tier.value, f.region or "",
                                 f.relationship_state.value, f.primary_focus or "",
                                 f.notes_summary or ""])
        elif entity_type == "partner":
            writer.writerow(["ulid", "firm_name", "name", "title", "practice", "seniority",
                             "email", "relationship_state", "last_contact_date",
                             "next_touch_date", "next_touch_topic"])
            for firm in firms_repo.list_firms(ctx.conn):
                for p in partners_repo.list_partners_by_firm(ctx.conn, firm.id):
                    writer.writerow([
                        p.ulid, firm.name, p.name, p.title or "", p.practice or "",
                        p.seniority or "", p.email or "", p.relationship_state.value,
                        p.last_contact_date.isoformat() if p.last_contact_date else "",
                        p.next_touch_date.isoformat() if p.next_touch_date else "",
                        p.next_touch_topic or "",
                    ])
        elif entity_type == "contact":
            writer.writerow(["ulid", "firm_name", "partner_name", "contact_date", "channel",
                             "initiated_by", "summary", "value_given", "value_received",
                             "follow_up"])
            for firm in firms_repo.list_firms(ctx.conn):
                for p in partners_repo.list_partners_by_firm(ctx.conn, firm.id):
                    for c in contacts_repo.list_contacts_by_partner(ctx.conn, p.id):
                        writer.writerow([
                            c.ulid, firm.name, p.name, c.contact_date.isoformat(),
                            c.channel.value, c.initiated_by.value,
                            c.summary or "", c.value_given or "",
                            c.value_received or "", c.follow_up or "",
                        ])
        else:
            raise ValueError(f"unsupported entity_type for CSV export: {entity_type}")
        return buf.getvalue()
