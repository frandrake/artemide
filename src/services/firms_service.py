"""Firms service. State transitions, soft delete, restore."""
from __future__ import annotations

from typing import Any

from ..models import (
    AuditAction,
    FirmRecord,
    FirmTier,
    FirmUpdateInput,
    RelationshipState,
)
from ..repository import firms as firms_repo
from ..repository import partners as partners_repo
from ..repository import search_index as search_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, InvalidStateTransitionError, NotFoundError, ValidationError


# Legal manual transitions. Auto-aging to dormant happens elsewhere.
_LEGAL_TRANSITIONS: dict[RelationshipState, set[RelationshipState]] = {
    RelationshipState.cold: {RelationshipState.warming, RelationshipState.dormant},
    RelationshipState.warming: {
        RelationshipState.warm,
        RelationshipState.cold,
        RelationshipState.dormant,
    },
    RelationshipState.warm: {RelationshipState.warming, RelationshipState.dormant},
    RelationshipState.dormant: {RelationshipState.warming},
}


def _record_to_dict(firm: FirmRecord) -> dict[str, Any]:
    d = firm.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _firm_search_text(firm: FirmRecord) -> tuple[str, str]:
    secondary = " ".join(
        filter(None, [firm.region, firm.primary_focus, firm.notes_summary])
    )
    return firm.name, secondary


class FirmsService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        tier: FirmTier | None = None,
        state: RelationshipState | None = None,
        include_deleted: bool = False,
    ) -> list[FirmRecord]:
        return firms_repo.list_firms(
            ctx.conn,
            tier=tier,
            relationship_state=state,
            include_deleted=include_deleted,
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> FirmRecord:
        firm = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
        if firm is None:
            raise NotFoundError(f"firm not found: {ulid}")
        return firm

    @staticmethod
    def get_by_name(ctx: ServiceContext, name: str) -> FirmRecord:
        firm = firms_repo.get_firm_by_name(ctx.conn, name)
        if firm is None:
            raise NotFoundError(f"firm not found: {name}")
        return firm

    @staticmethod
    def update_state(
        ctx: ServiceContext,
        ulid: str,
        new_state: RelationshipState,
    ) -> FirmRecord:
        with transaction(ctx.conn):
            firm = FirmsService.get_by_ulid(ctx, ulid)
            if firm.relationship_state == new_state:
                return firm
            allowed = _LEGAL_TRANSITIONS.get(firm.relationship_state, set())
            if new_state not in allowed:
                raise InvalidStateTransitionError(
                    f"illegal transition {firm.relationship_state.value} → {new_state.value}"
                )
            before = _record_to_dict(firm)
            updated = firms_repo.update_firm_fields(
                ctx.conn, firm.id, {"relationship_state": new_state}
            )
            assert updated is not None
            after = _record_to_dict(updated)
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="firm",
                entity_id=firm.id,
                entity_ulid=firm.ulid,
                before=before,
                after=after,
            )
            return updated

    @staticmethod
    def update_notes(ctx: ServiceContext, ulid: str, notes: str | None) -> FirmRecord:
        with transaction(ctx.conn):
            firm = FirmsService.get_by_ulid(ctx, ulid)
            before = _record_to_dict(firm)
            updated = firms_repo.update_firm_fields(ctx.conn, firm.id, {"notes_summary": notes})
            assert updated is not None
            primary, secondary = _firm_search_text(updated)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="firm",
                entity_ulid=updated.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            after = _record_to_dict(updated)
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="firm",
                entity_id=firm.id,
                entity_ulid=firm.ulid,
                before=before,
                after=after,
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: FirmUpdateInput) -> FirmRecord:
        with transaction(ctx.conn):
            firm = FirmsService.get_by_ulid(ctx, ulid)
            if firm.deleted_at is not None:
                raise NotFoundError(f"firm not found: {ulid}")
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            if "relationship_state" in raw:
                new_state = raw["relationship_state"]
                if firm.relationship_state != new_state:
                    allowed = _LEGAL_TRANSITIONS.get(firm.relationship_state, set())
                    if new_state not in allowed:
                        raise InvalidStateTransitionError(
                            f"illegal transition {firm.relationship_state.value} → {new_state.value}"
                        )
            if "notes" in raw:
                raw["notes_summary"] = raw.pop("notes")
            allowed_columns = {
                "tier", "region", "relationship_state", "notes_summary",
                "market_tier", "strategic_fit", "ned_practice_strength", "hq_address",
                "sectors", "cmo_practice_depth", "comp_transparency",
                "candidate_reputation", "b2b_fs_reputation",
            }
            fields = {
                k: v.value if hasattr(v, "value") else v
                for k, v in raw.items() if k in allowed_columns
            }
            before = _record_to_dict(firm)
            updated = firms_repo.update_firm_fields(ctx.conn, firm.id, fields)
            assert updated is not None
            primary, secondary = _firm_search_text(updated)
            search_repo.upsert_search_row(
                ctx.conn,
                entity_type="firm",
                entity_ulid=updated.ulid,
                primary_text=primary,
                secondary_text=secondary,
            )
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type="firm",
                entity_id=firm.id,
                entity_ulid=firm.ulid,
                before=before,
                after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete firm")
        with transaction(ctx.conn):
            firm = FirmsService.get_by_ulid(ctx, ulid)
            if firm.deleted_at is not None:
                raise ConflictError("firm already deleted")
            before = _record_to_dict(firm)
            firms_repo.soft_delete_firm(ctx.conn, firm.id)
            # Cascade: soft-delete all active partners atomically.
            active_partners = partners_repo.list_partners_by_firm(ctx.conn, firm.id, include_deleted=False)
            for p in active_partners:
                partners_repo.soft_delete_partner(ctx.conn, p.id)
                p_before = p.model_dump(mode="json")
                p_before = {k: v for k, v in p_before.items() if k not in ("created_at", "updated_at")}
                AuditService.record(
                    ctx,
                    action=AuditAction.delete,
                    entity_type="partner",
                    entity_id=p.id,
                    entity_ulid=p.ulid,
                    before=p_before,
                    after=None,
                )
            search_repo.delete_search_row(
                ctx.conn, entity_type="firm", entity_ulid=firm.ulid
            )
            AuditService.record(
                ctx,
                action=AuditAction.delete,
                entity_type="firm",
                entity_id=firm.id,
                entity_ulid=firm.ulid,
                before=before,
                after=None,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> FirmRecord:
        assert_owner(ctx, operation="restore firm")
        with transaction(ctx.conn):
            firm = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
            if firm is None:
                raise NotFoundError(f"firm not found: {ulid}")
            if firm.deleted_at is None:
                return firm
            return FirmsService._restore_internal(ctx, firm)

    # Internal helpers — not part of the public API but used by ImportService.

    @staticmethod
    def _restore_internal(ctx: ServiceContext, firm: FirmRecord) -> FirmRecord:
        """Un-delete a firm and re-index it. No owner gate and no transaction of
        its own — the caller supplies both (restore() and ImportService)."""
        firms_repo.restore_firm(ctx.conn, firm.id)
        restored = firms_repo.get_firm_by_id(ctx.conn, firm.id) or firm
        primary, secondary = _firm_search_text(restored)
        search_repo.upsert_search_row(
            ctx.conn,
            entity_type="firm",
            entity_ulid=restored.ulid,
            primary_text=primary,
            secondary_text=secondary,
        )
        AuditService.record(
            ctx,
            action=AuditAction.restore,
            entity_type="firm",
            entity_id=restored.id,
            entity_ulid=restored.ulid,
            before=None,
            after=_record_to_dict(restored),
        )
        return restored

    @staticmethod
    def _create_internal(
        ctx: ServiceContext,
        *,
        name: str,
        tier: FirmTier,
        region: str | None = None,
        relationship_state: RelationshipState = RelationshipState.cold,
        primary_focus: str | None = None,
        notes_summary: str | None = None,
    ) -> FirmRecord:
        firm = firms_repo.insert_firm(
            ctx.conn,
            name=name,
            tier=tier,
            region=region,
            relationship_state=relationship_state,
            primary_focus=primary_focus,
            notes_summary=notes_summary,
        )
        primary, secondary = _firm_search_text(firm)
        search_repo.upsert_search_row(
            ctx.conn,
            entity_type="firm",
            entity_ulid=firm.ulid,
            primary_text=primary,
            secondary_text=secondary,
        )
        AuditService.record(
            ctx,
            action=AuditAction.create,
            entity_type="firm",
            entity_id=firm.id,
            entity_ulid=firm.ulid,
            before=None,
            after=_record_to_dict(firm),
        )
        return firm

    @staticmethod
    def _update_internal(
        ctx: ServiceContext,
        *,
        firm: FirmRecord,
        fields: dict[str, Any],
    ) -> FirmRecord:
        before = _record_to_dict(firm)
        updated = firms_repo.update_firm_fields(ctx.conn, firm.id, fields)
        assert updated is not None
        primary, secondary = _firm_search_text(updated)
        search_repo.upsert_search_row(
            ctx.conn,
            entity_type="firm",
            entity_ulid=updated.ulid,
            primary_text=primary,
            secondary_text=secondary,
        )
        AuditService.record(
            ctx,
            action=AuditAction.update,
            entity_type="firm",
            entity_id=firm.id,
            entity_ulid=firm.ulid,
            before=before,
            after=_record_to_dict(updated),
        )
        return updated
