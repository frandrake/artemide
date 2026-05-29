"""OrgsService — organisations of interest in the programme."""
from __future__ import annotations

import json
from typing import Any

from ..models import AuditAction, OrganisationRecord, OrgUpdateInput, UpsertOrgInput, WatchState
from ..repository import orgs as orgs_repo
from ..repository import search_index as search_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError


def _record_to_dict(org: OrganisationRecord) -> dict[str, Any]:
    d = org.model_dump(mode="json")
    return {k: v for k, v in d.items() if k not in ("created_at", "updated_at")}


def _search_text(org: OrganisationRecord) -> tuple[str, str]:
    secondary = " ".join(p for p in (org.sector, org.hq_region, org.pertinence_note) if p)
    return org.name, secondary


def _index(ctx: ServiceContext, org: OrganisationRecord) -> None:
    primary, secondary = _search_text(org)
    search_repo.upsert_search_row(
        ctx.conn, entity_type="org", entity_ulid=org.ulid,
        primary_text=primary, secondary_text=secondary,
    )


class OrgsService:

    @staticmethod
    def list(
        ctx: ServiceContext,
        *,
        watch_state: Any = None,
        scale_band: Any = None,
        sector: str | None = None,
    ) -> list[OrganisationRecord]:
        return orgs_repo.list_orgs(
            ctx.conn, watch_state=watch_state, scale_band=scale_band, sector=sector
        )

    @staticmethod
    def get_by_ulid(ctx: ServiceContext, ulid: str) -> OrganisationRecord:
        org = orgs_repo.get_org_by_ulid(ctx.conn, ulid)
        if org is None:
            raise NotFoundError(f"organisation not found: {ulid}")
        return org

    @staticmethod
    def get_by_name(ctx: ServiceContext, name: str) -> OrganisationRecord | None:
        return orgs_repo.get_org_by_name(ctx.conn, name)

    @staticmethod
    def upsert(ctx: ServiceContext, data: UpsertOrgInput) -> OrganisationRecord:
        with transaction(ctx.conn):
            external_refs = json.dumps(data.external_refs) if data.external_refs else None
            existing = None
            if data.ulid:
                existing = orgs_repo.get_org_by_ulid(ctx.conn, data.ulid)
            if existing is None:
                existing = orgs_repo.get_org_by_name(ctx.conn, data.name)

            if existing is None:
                org = orgs_repo.insert_org(
                    ctx.conn,
                    name=data.name,
                    sector=data.sector,
                    scale_band=data.scale_band,
                    hq_region=data.hq_region,
                    pertinence_note=data.pertinence_note,
                    watch_state=data.watch_state or WatchState.watch,
                    source=data.source,
                    external_refs=external_refs,
                    ulid=data.ulid,
                )
                _index(ctx, org)
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="org",
                    entity_id=org.id, entity_ulid=org.ulid, after=_record_to_dict(org),
                )
                return org

            before = _record_to_dict(existing)
            fields = data.model_dump(exclude_none=True, exclude={"ulid", "name"})
            if "external_refs" in fields:
                fields["external_refs"] = external_refs
            updated = orgs_repo.update_org_fields(ctx.conn, existing.id, fields) or existing
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="org",
                entity_id=updated.id, entity_ulid=updated.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def update_fields(ctx: ServiceContext, ulid: str, data: OrgUpdateInput) -> OrganisationRecord:
        with transaction(ctx.conn):
            org = OrgsService.get_by_ulid(ctx, ulid)
            raw = data.model_dump(exclude_none=True)
            if not raw:
                raise ValidationError("no fields supplied")
            if "external_refs" in raw:
                raw["external_refs"] = json.dumps(raw["external_refs"])
            before = _record_to_dict(org)
            updated = orgs_repo.update_org_fields(ctx.conn, org.id, raw) or org
            _index(ctx, updated)
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="org",
                entity_id=org.id, entity_ulid=org.ulid,
                before=before, after=_record_to_dict(updated),
            )
            return updated

    @staticmethod
    def set_watch_state(ctx: ServiceContext, ulid: str, watch_state: WatchState) -> OrganisationRecord:
        return OrgsService.update_fields(ctx, ulid, OrgUpdateInput(watch_state=watch_state))

    @staticmethod
    def soft_delete(ctx: ServiceContext, ulid: str) -> None:
        assert_owner(ctx, operation="delete organisation")
        with transaction(ctx.conn):
            org = OrgsService.get_by_ulid(ctx, ulid)
            if org.deleted_at is not None:
                raise ConflictError("organisation already deleted")
            before = _record_to_dict(org)
            orgs_repo.soft_delete_org(ctx.conn, org.id)
            search_repo.delete_search_row(ctx.conn, entity_type="org", entity_ulid=org.ulid)
            AuditService.record(
                ctx, action=AuditAction.delete, entity_type="org",
                entity_id=org.id, entity_ulid=org.ulid, before=before,
            )

    @staticmethod
    def restore(ctx: ServiceContext, ulid: str) -> OrganisationRecord:
        assert_owner(ctx, operation="restore organisation")
        with transaction(ctx.conn):
            org = orgs_repo.get_org_by_ulid(ctx.conn, ulid)
            if org is None:
                raise NotFoundError(f"organisation not found: {ulid}")
            if org.deleted_at is None:
                return org
            orgs_repo.restore_org(ctx.conn, org.id)
            restored = orgs_repo.get_org_by_ulid(ctx.conn, ulid)
            assert restored is not None
            _index(ctx, restored)
            AuditService.record(
                ctx, action=AuditAction.restore, entity_type="org",
                entity_id=restored.id, entity_ulid=restored.ulid, after=_record_to_dict(restored),
            )
            return restored
