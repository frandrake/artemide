"""Owner-only, preview-only AI intake lifecycle for separated workstreams."""
from __future__ import annotations

import json
import re
from typing import Any

from ..models import AuditAction
from ..repository import intake_previews as previews_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import ConflictError, NotFoundError, ValidationError

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_STATUSES = {"draft", "confirmed", "rejected"}


def _require_json(value: Any, *, field: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be JSON serializable") from exc


def _validate_metadata(
    *,
    proposed_payload: dict[str, Any],
    provider: str,
    model: str,
    prompt: str,
    input_hash: str,
    sources: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> None:
    if not isinstance(proposed_payload, dict) or not proposed_payload:
        raise ValidationError("proposed_payload must be a non-empty JSON object")
    for field, value in (("provider", provider), ("model", model), ("prompt", prompt)):
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{field} is required")
    if not isinstance(input_hash, str) or _SHA256.fullmatch(input_hash) is None:
        raise ValidationError("input_hash must be a 64-character SHA-256 hex digest")
    if not isinstance(sources, list) or not sources or any(not isinstance(item, dict) for item in sources):
        raise ValidationError("sources must be a non-empty JSON array of objects")
    if not isinstance(provenance, dict):
        raise ValidationError("provenance must be a JSON object")
    _require_json(proposed_payload, field="proposed_payload")
    _require_json(sources, field="sources")
    _require_json(provenance, field="provenance")


def _audit_projection(preview: dict[str, Any]) -> dict[str, Any]:
    """Audit lifecycle metadata without copying intake payload/source contents."""
    return {
        "ulid": preview["ulid"],
        "status": preview["status"],
        "provider": preview["provider"],
        "model": preview["model"],
        "input_hash": preview["input_hash"],
        "created_by": preview["created_by"],
        "confirmed_by": preview["confirmed_by"],
        "rejected_by": preview["rejected_by"],
        "confirmed_at": preview["confirmed_at"],
        "rejected_at": preview["rejected_at"],
    }


class IntakeService:
    """Persist and review AI proposals; never apply them to canonical records."""

    @staticmethod
    def _create(
        ctx: ServiceContext,
        *,
        domain: previews_repo.Domain,
        proposed_payload: dict[str, Any],
        provider: str,
        model: str,
        prompt: str,
        input_hash: str,
        sources: list[dict[str, Any]],
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        assert_owner(ctx, operation=f"create {domain} AI intake preview")
        _validate_metadata(
            proposed_payload=proposed_payload,
            provider=provider,
            model=model,
            prompt=prompt,
            input_hash=input_hash,
            sources=sources,
            provenance=provenance,
        )
        with transaction(ctx.conn):
            preview = previews_repo.insert_preview(
                ctx.conn,
                domain=domain,
                proposed_payload=proposed_payload,
                provider=provider.strip(),
                model=model.strip(),
                prompt=prompt.strip(),
                input_hash=input_hash.lower(),
                sources=sources,
                provenance=provenance,
                created_by=ctx.actor,
            )
            AuditService.record(
                ctx,
                action=AuditAction.create,
                entity_type=f"{domain}_ai_intake_preview",
                entity_id=preview["id"],
                entity_ulid=preview["ulid"],
                after=_audit_projection(preview),
            )
        return preview

    @staticmethod
    def create_executive_preview(ctx: ServiceContext, **kwargs: Any) -> dict[str, Any]:
        return IntakeService._create(ctx, domain="executive", **kwargs)

    @staticmethod
    def create_board_preview(ctx: ServiceContext, **kwargs: Any) -> dict[str, Any]:
        return IntakeService._create(ctx, domain="board", **kwargs)

    @staticmethod
    def _get(ctx: ServiceContext, domain: previews_repo.Domain, ulid: str) -> dict[str, Any]:
        assert_owner(ctx, operation=f"read {domain} AI intake preview")
        preview = previews_repo.get_preview_by_ulid(ctx.conn, domain=domain, ulid=ulid)
        if preview is None:
            raise NotFoundError(f"{domain} AI intake preview not found: {ulid}")
        return preview

    @staticmethod
    def get_executive_preview(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        return IntakeService._get(ctx, "executive", ulid)

    @staticmethod
    def get_board_preview(ctx: ServiceContext, ulid: str) -> dict[str, Any]:
        return IntakeService._get(ctx, "board", ulid)

    @staticmethod
    def _list(
        ctx: ServiceContext, domain: previews_repo.Domain, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        assert_owner(ctx, operation=f"list {domain} AI intake previews")
        if status is not None and status not in _STATUSES:
            raise ValidationError(f"invalid preview status: {status}")
        return previews_repo.list_previews(ctx.conn, domain=domain, status=status)

    @staticmethod
    def list_executive_previews(
        ctx: ServiceContext, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        return IntakeService._list(ctx, "executive", status=status)

    @staticmethod
    def list_board_previews(
        ctx: ServiceContext, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        return IntakeService._list(ctx, "board", status=status)

    @staticmethod
    def _confirm(
        ctx: ServiceContext,
        domain: previews_repo.Domain,
        ulid: str,
        *,
        corrected_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation=f"confirm {domain} AI intake preview")
        if corrected_payload is not None and (
            not isinstance(corrected_payload, dict) or not corrected_payload
        ):
            raise ValidationError("corrected_payload must be a non-empty JSON object")
        if corrected_payload is not None:
            _require_json(corrected_payload, field="corrected_payload")
        with transaction(ctx.conn):
            before = IntakeService._get(ctx, domain, ulid)
            if before["status"] != "draft":
                raise ConflictError(f"preview is already {before['status']}")
            changed = previews_repo.confirm_preview(
                ctx.conn,
                domain=domain,
                preview_id=before["id"],
                confirmed_by=ctx.actor,
                corrected_payload=corrected_payload,
            )
            if not changed:
                raise ConflictError("preview is no longer draft")
            after = previews_repo.get_preview_by_ulid(ctx.conn, domain=domain, ulid=ulid)
            assert after is not None
            # Deliberately no canonical service call, outbox event, or search indexing.
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type=f"{domain}_ai_intake_preview",
                entity_id=after["id"],
                entity_ulid=ulid,
                before=_audit_projection(before),
                after=_audit_projection(after),
            )
        return after

    @staticmethod
    def confirm_executive_preview(
        ctx: ServiceContext, ulid: str, *, corrected_payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return IntakeService._confirm(
            ctx, "executive", ulid, corrected_payload=corrected_payload
        )

    @staticmethod
    def confirm_board_preview(
        ctx: ServiceContext, ulid: str, *, corrected_payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return IntakeService._confirm(ctx, "board", ulid, corrected_payload=corrected_payload)

    @staticmethod
    def _reject(
        ctx: ServiceContext,
        domain: previews_repo.Domain,
        ulid: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        assert_owner(ctx, operation=f"reject {domain} AI intake preview")
        if reason is not None:
            reason = reason.strip()
            if not reason:
                raise ValidationError("rejection reason cannot be blank")
        with transaction(ctx.conn):
            before = IntakeService._get(ctx, domain, ulid)
            if before["status"] != "draft":
                raise ConflictError(f"preview is already {before['status']}")
            changed = previews_repo.reject_preview(
                ctx.conn,
                domain=domain,
                preview_id=before["id"],
                rejected_by=ctx.actor,
                reason=reason,
            )
            if not changed:
                raise ConflictError("preview is no longer draft")
            after = previews_repo.get_preview_by_ulid(ctx.conn, domain=domain, ulid=ulid)
            assert after is not None
            AuditService.record(
                ctx,
                action=AuditAction.update,
                entity_type=f"{domain}_ai_intake_preview",
                entity_id=after["id"],
                entity_ulid=ulid,
                before=_audit_projection(before),
                after=_audit_projection(after),
            )
        return after

    @staticmethod
    def reject_executive_preview(
        ctx: ServiceContext, ulid: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        return IntakeService._reject(ctx, "executive", ulid, reason=reason)

    @staticmethod
    def reject_board_preview(
        ctx: ServiceContext, ulid: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        return IntakeService._reject(ctx, "board", ulid, reason=reason)
