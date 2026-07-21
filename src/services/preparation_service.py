"""Preparation-pack lifecycle with immutable content and cited provenance."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from ..models import AuditAction
from ..repository import preparation_packs as repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_sources(content: str, sources: list[dict[str, Any]]) -> None:
    if not sources:
        raise ValidationError("at least one cited source is required")
    labels: set[str] = set()
    for source in sources:
        required = ("source_kind", "sha256", "retrieved_at", "citation_label")
        if any(not source.get(key) for key in required):
            raise ValidationError("every source requires kind, sha256, retrieval time and citation label")
        label = str(source["citation_label"]).strip()
        if label in labels:
            raise ValidationError("citation labels must be unique within a pack")
        labels.add(label)
        if label not in content:
            raise ValidationError(f"content must cite source label: {label}")
        digest = str(source["sha256"])
        if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
            raise ValidationError("source sha256 must be a 64-character hexadecimal digest")
        source_ulid = source.get("source_ulid")
        public_url = source.get("public_url")
        if bool(source_ulid) == bool(public_url):
            raise ValidationError("each source must have exactly one source_ulid or public_url")
        if public_url:
            parsed = urlparse(str(public_url))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValidationError("public_url must be an absolute HTTP(S) URL")
        try:
            datetime.fromisoformat(str(source["retrieved_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError("retrieved_at must be an ISO-8601 timestamp") from exc


def _validate_proposal(
    *, content: str, generated_by: str, sources: list[dict[str, Any]], target: str,
) -> None:
    if not target.strip():
        raise ValidationError("preparation-pack target is required")
    if not content.strip():
        raise ValidationError("preparation-pack content is required")
    if not generated_by.strip():
        raise ValidationError("generated_by is required")
    _validate_sources(content, sources)


def _audit_metadata(pack: dict[str, Any]) -> dict[str, Any]:
    """Audit only non-content metadata; especially never leak board material."""
    result = {
        "ulid": pack["ulid"], "version": pack["version"], "status": pack["status"],
        "content_sha256": pack["content_sha256"], "source_count": len(pack["sources"]),
    }
    if "target_entity_type" in pack:
        result["target_entity_type"] = pack["target_entity_type"]
        result["target_entity_ulid"] = pack["target_entity_ulid"]
    return result


class PreparationService:
    @staticmethod
    def propose_executive(
        ctx: ServiceContext, *, target_entity_type: str, target_entity_ulid: str,
        content: str, sources: list[dict[str, Any]], generated_by: str,
        model: str | None = None, prompt_version: str | None = None,
        generation_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation="propose executive preparation pack")
        _validate_proposal(
            content=content, generated_by=generated_by, sources=sources,
            target=target_entity_ulid,
        )
        if not target_entity_type.strip():
            raise ValidationError("target_entity_type is required")
        proposed_at = _utc_now()
        with transaction(ctx.conn):
            pack = repo.insert_executive_pack(
                ctx.conn, target_entity_type=target_entity_type,
                target_entity_ulid=target_entity_ulid, content=content,
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                generated_by=generated_by, model=model, prompt_version=prompt_version,
                generation_metadata=generation_metadata, proposed_by=ctx.actor,
                proposed_at=proposed_at, sources=sources,
            )
            AuditService.record(
                ctx, action=AuditAction.create, entity_type="executive_preparation_pack",
                entity_id=pack["id"], entity_ulid=pack["ulid"], after=_audit_metadata(pack),
            )
        return pack

    @staticmethod
    def get_executive(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="read executive preparation pack")
        pack = repo.get_executive_pack(ctx.conn, ulid)
        if pack is None:
            raise NotFoundError(f"executive preparation pack not found: {ulid}")
        return pack

    @staticmethod
    def list_executive(
        ctx: ServiceContext, *, target_entity_type: str, target_entity_ulid: str,
    ) -> list[dict[str, Any]]:
        assert_owner(ctx, operation="list executive preparation packs")
        return repo.list_executive_packs(
            ctx.conn, target_entity_type=target_entity_type,
            target_entity_ulid=target_entity_ulid,
        )

    @staticmethod
    def confirm_executive(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="confirm executive preparation pack")
        with transaction(ctx.conn):
            pack = repo.get_executive_pack(ctx.conn, ulid)
            if pack is None:
                raise NotFoundError(f"executive preparation pack not found: {ulid}")
            if pack["status"] != "proposed":
                raise ConflictError("only a proposed preparation pack can be confirmed")
            confirmed_at = _utc_now()
            repo.confirm_executive_pack(
                ctx.conn, pack_id=pack["id"], target_entity_type=pack["target_entity_type"],
                target_entity_ulid=pack["target_entity_ulid"], actor=ctx.actor,
                confirmed_at=confirmed_at,
            )
            confirmed = repo.get_executive_pack(ctx.conn, ulid)
            assert confirmed is not None
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="executive_preparation_pack",
                entity_id=confirmed["id"], entity_ulid=confirmed["ulid"],
                before=_audit_metadata(pack), after=_audit_metadata(confirmed),
            )
        return confirmed

    @staticmethod
    def propose_board(
        ctx: ServiceContext, *, board_opportunity_ulid: str, content: str,
        sources: list[dict[str, Any]], generated_by: str, model: str | None = None,
        prompt_version: str | None = None,
        generation_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation="propose board preparation pack")
        _validate_proposal(
            content=content, generated_by=generated_by, sources=sources,
            target=board_opportunity_ulid,
        )
        proposed_at = _utc_now()
        with transaction(ctx.conn):
            pack = repo.insert_board_pack(
                ctx.conn, board_opportunity_ulid=board_opportunity_ulid, content=content,
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                generated_by=generated_by, model=model, prompt_version=prompt_version,
                generation_metadata=generation_metadata, proposed_by=ctx.actor,
                proposed_at=proposed_at, sources=sources,
            )
            AuditService.record(
                ctx, action=AuditAction.create, entity_type="board_preparation_pack",
                entity_id=pack["id"], entity_ulid=pack["ulid"], after=_audit_metadata(pack),
            )
        return pack

    @staticmethod
    def get_board(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="read board preparation pack")
        pack = repo.get_board_pack(ctx.conn, ulid)
        if pack is None:
            raise NotFoundError(f"board preparation pack not found: {ulid}")
        return pack

    @staticmethod
    def list_board(
        ctx: ServiceContext, *, board_opportunity_ulid: str,
    ) -> list[dict[str, Any]]:
        assert_owner(ctx, operation="list board preparation packs")
        return repo.list_board_packs(ctx.conn, board_opportunity_ulid=board_opportunity_ulid)

    @staticmethod
    def confirm_board(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation="confirm board preparation pack")
        with transaction(ctx.conn):
            pack = repo.get_board_pack(ctx.conn, ulid)
            if pack is None:
                raise NotFoundError(f"board preparation pack not found: {ulid}")
            if pack["status"] != "proposed":
                raise ConflictError("only a proposed preparation pack can be confirmed")
            confirmed_at = _utc_now()
            repo.confirm_board_pack(
                ctx.conn, pack_id=pack["id"],
                board_opportunity_ulid=pack["board_opportunity_ulid"], actor=ctx.actor,
                confirmed_at=confirmed_at,
            )
            confirmed = repo.get_board_pack(ctx.conn, ulid)
            assert confirmed is not None
            AuditService.record(
                ctx, action=AuditAction.update, entity_type="board_preparation_pack",
                entity_id=confirmed["id"], entity_ulid=confirmed["ulid"],
                before=_audit_metadata(pack), after=_audit_metadata(confirmed),
            )
        return confirmed
