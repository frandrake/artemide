"""Board import service. Idempotent markdown ledger ingest for the board domain.

Seeds the tiered firm/contact list. Parse-fully-then-one-transaction; dedupe is
inherited from the upsert services (firm by name, contact by (firm, name)), so a
re-import is a no-op. Owner-only (the upsert services each assert_owner).

Ledger grammar:
  ## Tier: <1-4>
  ### Firm: <name>
    - **Type:** boutique
    - **Geography:** UK, Italy
    - **Sectors:** ...
    - **AI-hook:** ...
    - **Status:** to_approach
    - **Next-action:** ...
    - **Source-url:** ...
    - **Notes:** ...
  #### Contact: <name>
    - **Role:** ...
    - **Practice:** board
    - **Email:** ...
    - **LinkedIn:** ...
    - **Mutual:** ...
    - **Relationship:** warm
    - **Last-contact:** 2026-05-01
    - **Source-url:** ...
    - **Notes:** ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..models import (
    AuditAction,
    UpsertBoardContactInput,
    UpsertBoardFirmInput,
)
from ..repository import board_firms as firms_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .board_contacts_service import BoardContactsService
from .board_firms_service import BoardFirmsService
from .exceptions import ValidationError

_KV_LINE = re.compile(r"^\s*-\s+\*\*([A-Za-z-]+):\*\*\s+(.+?)\s*$")

_FIRM_KV_MAP = {
    "type": "firm_type",
    "geography": "geography",
    "sectors": "sectors_level",
    "ai-hook": "ai_on_boards_hook",
    "status": "status",
    "next-action": "next_action",
    "source-url": "source_url",
    "notes": "notes",
}
_CONTACT_KV_MAP = {
    "role": "role_title",
    "practice": "practice",
    "email": "email",
    "linkedin": "linkedin",
    "mutual": "mutual_connections",
    "relationship": "relationship",
    "last-contact": "last_contact_date",
    "source-url": "source_url",
    "notes": "notes",
}


@dataclass
class BoardImportSummary:
    firms_created: int = 0
    firms_updated: int = 0
    contacts_created: int = 0
    contacts_updated: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class _ParsedFirm:
    name: str
    tier: int | None = None
    fields: dict = field(default_factory=dict)
    contacts: list["_ParsedContact"] = field(default_factory=list)


@dataclass
class _ParsedContact:
    name: str
    fields: dict = field(default_factory=dict)


def _parse(content: str) -> list[_ParsedFirm]:
    firms: list[_ParsedFirm] = []
    current_tier: int | None = None
    current_firm: _ParsedFirm | None = None
    current_contact: _ParsedContact | None = None

    for raw in content.splitlines():
        line = raw.rstrip()
        if line.startswith("## Tier:"):
            current_tier = int(line.split(":", 1)[1].strip())
            current_firm = current_contact = None
            continue
        if line.startswith("### Firm:"):
            name = line.split(":", 1)[1].strip()
            current_firm = _ParsedFirm(name=name, tier=current_tier)
            firms.append(current_firm)
            current_contact = None
            continue
        if line.startswith("#### Contact:") and current_firm is not None:
            name = line.split(":", 1)[1].strip()
            current_contact = _ParsedContact(name=name)
            current_firm.contacts.append(current_contact)
            continue

        kv = _KV_LINE.match(line)
        if kv:
            key = kv.group(1).strip().lower()
            value = kv.group(2).strip()
            if current_contact is not None and key in _CONTACT_KV_MAP:
                current_contact.fields[_CONTACT_KV_MAP[key]] = value
            elif current_firm is not None and current_contact is None and key in _FIRM_KV_MAP:
                current_firm.fields[_FIRM_KV_MAP[key]] = value
            continue
    return firms


def _firm_input(parsed: _ParsedFirm) -> UpsertBoardFirmInput:
    data = dict(parsed.fields)
    geo = data.pop("geography", None)
    geography = [g.strip() for g in geo.split(",") if g.strip()] if geo else None
    return UpsertBoardFirmInput(
        name=parsed.name, tier=parsed.tier, geography=geography, **data
    )


def _contact_input(parsed: _ParsedContact, firm_ulid: str) -> UpsertBoardContactInput:
    data = dict(parsed.fields)
    if "last_contact_date" in data:
        data["last_contact_date"] = date.fromisoformat(data["last_contact_date"])
    return UpsertBoardContactInput(name=parsed.name, firm_ulid=firm_ulid, **data)


class BoardImportService:

    @staticmethod
    def import_markdown(ctx: ServiceContext, content: str) -> BoardImportSummary:
        assert_owner(ctx, operation="import board ledger")
        summary = BoardImportSummary()
        try:
            parsed_firms = _parse(content)
        except Exception as e:
            raise ValidationError(f"could not parse board ledger: {e}") from e

        with transaction(ctx.conn):
            for pfirm in parsed_firms:
                try:
                    pre_existing = firms_repo.get_firm_by_name(ctx.conn, pfirm.name)
                    firm = BoardFirmsService.upsert(ctx, _firm_input(pfirm))
                    if pre_existing is None:
                        summary.firms_created += 1
                    else:
                        summary.firms_updated += 1
                except Exception as e:  # noqa: BLE001 — record and continue seeding
                    summary.errors.append(f"firm '{pfirm.name}': {e}")
                    continue

                for pcontact in pfirm.contacts:
                    try:
                        pre = next(
                            (c for c in BoardContactsService.list(ctx, firm_ulid=firm.ulid)
                             if c.name == pcontact.name),
                            None,
                        )
                        BoardContactsService.upsert(ctx, _contact_input(pcontact, firm.ulid))
                        if pre is None:
                            summary.contacts_created += 1
                        else:
                            summary.contacts_updated += 1
                    except Exception as e:  # noqa: BLE001
                        summary.errors.append(f"contact '{pcontact.name}': {e}")

            AuditService.record(
                ctx, action=AuditAction.import_, entity_type="board_ledger",
                entity_ulid=None,
                after={
                    "firms_created": summary.firms_created,
                    "firms_updated": summary.firms_updated,
                    "contacts_created": summary.contacts_created,
                    "contacts_updated": summary.contacts_updated,
                    "errors": len(summary.errors),
                },
            )
        return summary
