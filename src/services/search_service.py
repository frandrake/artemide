"""Search service. FTS5-backed across firms, partners, notes, contacts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..repository import contacts as contacts_repo
from ..repository import firms as firms_repo
from ..repository import notes as notes_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, transaction


@dataclass
class SearchHit:
    entity_type: str
    entity_ulid: str
    primary_text: str
    secondary_text: str
    rank: float
    entity: dict[str, Any] | None


def _firm_text(firm) -> tuple[str, str]:
    secondary = " ".join(filter(None, [firm.region, firm.primary_focus, firm.notes_summary]))
    return firm.name, secondary


def _partner_text(partner, firm_name: str) -> tuple[str, str]:
    secondary = " ".join(filter(None, [
        firm_name, partner.title, partner.practice, partner.seniority, partner.notes_summary,
    ]))
    return partner.name, secondary


def _note_text(note, label: str) -> tuple[str, str]:
    return label, note.body


def _contact_text(contact, partner_name: str) -> tuple[str, str]:
    secondary = " ".join(filter(None, [
        partner_name, contact.summary, contact.value_given, contact.value_received, contact.follow_up,
    ]))
    return f"{partner_name} — {contact.contact_date.isoformat()}", secondary


class SearchService:

    @staticmethod
    def search(
        ctx: ServiceContext,
        *,
        query: str,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[SearchHit]:
        if not query.strip():
            return []
        raw = search_repo.search(ctx.conn, query=query, entity_type=entity_type, limit=limit)
        hits: list[SearchHit] = []
        for row in raw:
            et = row["entity_type"]
            eu = row["entity_ulid"]
            entity: dict[str, Any] | None = None
            if et == "firm":
                f = firms_repo.get_firm_by_ulid(ctx.conn, eu)
                if f:
                    entity = f.model_dump(mode="json")
            elif et == "partner":
                p = partners_repo.get_partner_by_ulid(ctx.conn, eu)
                if p:
                    entity = p.model_dump(mode="json")
            elif et == "note":
                n = notes_repo.get_note_by_ulid(ctx.conn, eu)
                if n:
                    entity = n.model_dump(mode="json")
            elif et == "contact":
                c = contacts_repo.get_contact_by_ulid(ctx.conn, eu)
                if c:
                    entity = c.model_dump(mode="json")
            hits.append(SearchHit(
                entity_type=et,
                entity_ulid=eu,
                primary_text=row["primary_text"],
                secondary_text=row["secondary_text"],
                rank=float(row["rank"]),
                entity=entity,
            ))
        return hits

    @staticmethod
    def rebuild_index(ctx: ServiceContext) -> int:
        with transaction(ctx.conn):
            ctx.conn.execute("DELETE FROM search_index")
            count = 0
            for firm in firms_repo.list_firms(ctx.conn, include_deleted=False):
                primary, secondary = _firm_text(firm)
                search_repo.upsert_search_row(
                    ctx.conn,
                    entity_type="firm",
                    entity_ulid=firm.ulid,
                    primary_text=primary,
                    secondary_text=secondary,
                )
                count += 1
                for p in partners_repo.list_partners_by_firm(ctx.conn, firm.id):
                    pprimary, psecondary = _partner_text(p, firm.name)
                    search_repo.upsert_search_row(
                        ctx.conn,
                        entity_type="partner",
                        entity_ulid=p.ulid,
                        primary_text=pprimary,
                        secondary_text=psecondary,
                    )
                    count += 1
                    for c in contacts_repo.list_contacts_by_partner(ctx.conn, p.id):
                        if not (c.summary or c.value_given or c.value_received):
                            continue
                        cprimary, csecondary = _contact_text(c, p.name)
                        search_repo.upsert_search_row(
                            ctx.conn,
                            entity_type="contact",
                            entity_ulid=c.ulid,
                            primary_text=cprimary,
                            secondary_text=csecondary,
                        )
                        count += 1
            for note_row in ctx.conn.execute(
                "SELECT ulid, entity_type, entity_id, body FROM notes"
            ).fetchall():
                entity_label = note_row["entity_type"] + ":" + note_row["entity_id"]
                search_repo.upsert_search_row(
                    ctx.conn,
                    entity_type="note",
                    entity_ulid=note_row["ulid"],
                    primary_text=entity_label,
                    secondary_text=note_row["body"],
                )
                count += 1
            return count
