"""Owner-only neutral identity service with explicit workstream links."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models import AuditAction
from ..repository import board_contacts as board_contacts_repo
from ..repository import partners as partners_repo
from ..repository import person_identity as identity_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError

_NEUTRAL_FIELDS = {
    "display_name",
    "preferred_name",
    "email",
    "linkedin_url",
    "current_title",
    "current_organisation",
    "location",
    "source_url",
}


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "id"}


def _require_identity(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
    record = identity_repo.get_identity_by_ulid(ctx.conn, ulid)
    if record is None:
        raise NotFoundError(f"person identity not found: {ulid}")
    return record


def _clean_optional(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field} cannot be blank")
    return cleaned


class PersonIdentityService:
    """Manage minimal public identity facts; never infer or expose relationships."""

    @staticmethod
    def create(
        ctx: ServiceContext,
        *,
        display_name: str,
        preferred_name: str | None = None,
        email: str | None = None,
        linkedin_url: str | None = None,
        current_title: str | None = None,
        current_organisation: str | None = None,
        location: str | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation="create person identity")
        name = display_name.strip()
        if not name:
            raise ValidationError("display_name is required")
        values = {
            "display_name": name,
            "preferred_name": _clean_optional(preferred_name, field="preferred_name"),
            "email": _clean_optional(email, field="email"),
            "linkedin_url": _clean_optional(linkedin_url, field="linkedin_url"),
            "current_title": _clean_optional(current_title, field="current_title"),
            "current_organisation": _clean_optional(
                current_organisation, field="current_organisation"
            ),
            "location": _clean_optional(location, field="location"),
            "source_url": _clean_optional(source_url, field="source_url"),
        }
        with transaction(ctx.conn):
            record = identity_repo.insert_identity(ctx.conn, **values)
            AuditService.record(
                ctx,
                action=AuditAction.create,
                entity_type="person_identity",
                entity_id=record["id"],
                entity_ulid=record["ulid"],
                after=_public_record(record),
            )
        return _public_record(record)

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="read person identity")
        return _public_record(_require_identity(ctx, ulid))

    @staticmethod
    def list(ctx: ServiceContext) -> list[dict[str, Any]]:
        assert_owner(ctx, operation="list person identities")
        return [_public_record(item) for item in identity_repo.list_identities(ctx.conn)]

    @staticmethod
    def update(ctx: ServiceContext, ulid: str, **fields: Any) -> dict[str, Any]:
        assert_owner(ctx, operation="update person identity")
        unknown = set(fields) - _NEUTRAL_FIELDS
        if unknown:
            raise ValidationError(f"unsupported identity fields: {', '.join(sorted(unknown))}")
        if not fields:
            raise ValidationError("no fields supplied")
        cleaned: dict[str, Any] = {}
        for key, value in fields.items():
            if key == "display_name":
                if not isinstance(value, str) or not value.strip():
                    raise ValidationError("display_name is required")
                cleaned[key] = value.strip()
            elif value is None:
                cleaned[key] = None
            elif not isinstance(value, str):
                raise ValidationError(f"{key} must be a string or null")
            else:
                cleaned[key] = _clean_optional(value, field=key)
        with transaction(ctx.conn):
            current = _require_identity(ctx, ulid)
            updated = identity_repo.update_identity_fields(ctx.conn, current["id"], cleaned)
            assert updated is not None
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="person_identity",
                entity_id=current["id"],
                entity_ulid=ulid,
                before=_public_record(current),
                after=_public_record(updated),
            )
        return _public_record(updated)

    @staticmethod
    def get_links(ctx: ServiceContext, person_ulid: str) -> dict[str, list[str]]:
        assert_owner(ctx, operation="read person identity links")
        person = _require_identity(ctx, person_ulid)
        return {
            "partner_ulids": identity_repo.list_partner_ulids(ctx.conn, person["id"]),
            "board_contact_ulids": identity_repo.list_board_contact_ulids(
                ctx.conn, person["id"]
            ),
        }

    @staticmethod
    def link_partner(ctx: ServiceContext, person_ulid: str, partner_ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="link executive person identity")
        with transaction(ctx.conn):
            person = _require_identity(ctx, person_ulid)
            partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if partner is None:
                raise NotFoundError(f"partner not found: {partner_ulid}")
            try:
                link = identity_repo.insert_executive_link(
                    ctx.conn,
                    person_identity_id=person["id"],
                    partner_id=partner.id,
                    linked_by=ctx.actor,
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError("partner is already linked to a person identity") from exc
            AuditService.record(
                ctx,
                action=AuditAction.create,
                entity_type="executive_person_link",
                entity_ulid=link["ulid"],
                after={"person_ulid": person_ulid, "partner_ulid": partner_ulid},
            )
            return {"ulid": link["ulid"], "person_ulid": person_ulid, "partner_ulid": partner_ulid}

    @staticmethod
    def link_board_contact(
        ctx: ServiceContext, person_ulid: str, board_contact_ulid: str
    ) -> dict[str, Any]:
        assert_owner(ctx, operation="link board person identity")
        with transaction(ctx.conn):
            person = _require_identity(ctx, person_ulid)
            contact = board_contacts_repo.get_contact_by_ulid(ctx.conn, board_contact_ulid)
            if contact is None:
                raise NotFoundError(f"board contact not found: {board_contact_ulid}")
            try:
                link = identity_repo.insert_board_link(
                    ctx.conn,
                    person_identity_id=person["id"],
                    board_contact_id=contact.id,
                    linked_by=ctx.actor,
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError("board contact is already linked to a person identity") from exc
            AuditService.record(
                ctx,
                action=AuditAction.create,
                entity_type="board_person_link",
                entity_ulid=link["ulid"],
                after={"person_ulid": person_ulid, "board_contact_ulid": board_contact_ulid},
            )
            return {
                "ulid": link["ulid"],
                "person_ulid": person_ulid,
                "board_contact_ulid": board_contact_ulid,
            }

    @staticmethod
    def unlink_partner(ctx: ServiceContext, person_ulid: str, partner_ulid: str) -> None:
        assert_owner(ctx, operation="unlink executive person identity")
        with transaction(ctx.conn):
            person = _require_identity(ctx, person_ulid)
            partner = partners_repo.get_partner_by_ulid(ctx.conn, partner_ulid)
            if partner is None or not identity_repo.delete_executive_link(
                ctx.conn, person_identity_id=person["id"], partner_id=partner.id
            ):
                raise NotFoundError("executive person link not found")
            AuditService.record(
                ctx,
                action=AuditAction.delete,
                entity_type="executive_person_link",
                entity_ulid=person_ulid,
                before={"person_ulid": person_ulid, "partner_ulid": partner_ulid},
            )

    @staticmethod
    def unlink_board_contact(
        ctx: ServiceContext, person_ulid: str, board_contact_ulid: str
    ) -> None:
        assert_owner(ctx, operation="unlink board person identity")
        with transaction(ctx.conn):
            person = _require_identity(ctx, person_ulid)
            contact = board_contacts_repo.get_contact_by_ulid(ctx.conn, board_contact_ulid)
            if contact is None or not identity_repo.delete_board_link(
                ctx.conn, person_identity_id=person["id"], board_contact_id=contact.id
            ):
                raise NotFoundError("board person link not found")
            AuditService.record(
                ctx,
                action=AuditAction.delete,
                entity_type="board_person_link",
                entity_ulid=person_ulid,
                before={
                    "person_ulid": person_ulid,
                    "board_contact_ulid": board_contact_ulid,
                },
            )
