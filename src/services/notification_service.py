"""Central policy for a redacted notification queue; never sends externally."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..models import AuditAction
from ..repository import notification_dispatch as repo
from . import ServiceContext, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError, ValidationError

_LONDON = ZoneInfo("Europe/London")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ALLOWED_PAYLOAD_KEYS = {"summary_code", "count", "workstream", "due_bucket", "action_code"}


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _quiet_hours_end(value: datetime) -> datetime:
    """Return earliest eligible UTC time under 20:00–07:29 London quiet hours."""
    local = value.astimezone(_LONDON)
    local_clock = local.timetz().replace(tzinfo=None)
    start = time(20, 0)
    end = time(7, 30)
    if local_clock >= start:
        eligible_date = local.date() + timedelta(days=1)
    elif local_clock < end:
        eligible_date = local.date()
    else:
        return value.astimezone(timezone.utc)
    eligible_local = datetime.combine(eligible_date, end, tzinfo=_LONDON)
    return eligible_local.astimezone(timezone.utc)


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = {key: payload[key] for key in _ALLOWED_PAYLOAD_KEYS if key in payload}
    summary_code = redacted.get("summary_code")
    if not isinstance(summary_code, str) or not _TOKEN.fullmatch(summary_code):
        raise ValidationError("payload summary_code must be a redacted uppercase code")
    for key in ("due_bucket", "action_code"):
        value = redacted.get(key)
        if value is not None and (not isinstance(value, str) or not _TOKEN.fullmatch(value)):
            raise ValidationError(f"payload {key} must be a redacted uppercase code")
    count = redacted.get("count")
    if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 0):
        raise ValidationError("payload count must be a non-negative integer")
    workstream = redacted.get("workstream")
    if workstream is not None and workstream not in {"executive", "board", "combined"}:
        raise ValidationError("payload workstream is invalid")
    return redacted


class NotificationService:
    """Queue/list/ack only. There is intentionally no send method or integration."""

    @staticmethod
    def queue(
        ctx: ServiceContext, *, notification_type: str, priority: str,
        dedupe_key: str, payload: dict[str, Any], now: datetime,
        expires_at: datetime, not_before: datetime | None = None,
    ) -> dict[str, Any]:
        if priority not in {"P1", "P2", "P3"}:
            raise ValidationError("priority must be P1, P2 or P3")
        if not notification_type.strip() or not dedupe_key.strip():
            raise ValidationError("notification_type and dedupe_key are required")
        queued_at = _aware(now, "now")
        expiry = _aware(expires_at, "expires_at")
        requested = _aware(not_before, "not_before") if not_before is not None else queued_at
        eligible = _quiet_hours_end(max(queued_at, requested))
        if expiry <= queued_at:
            raise ValidationError("expires_at must be after queued time")
        if expiry <= eligible:
            raise ValidationError("notification expires before it becomes eligible")
        redacted = _redact(payload)
        payload_json = json.dumps(redacted, sort_keys=True, separators=(",", ":"))
        # For P1 this represents the overdue episode, ensuring at most one alert.
        fingerprint = hashlib.sha256(
            f"{priority}\x1f{notification_type}\x1f{dedupe_key}".encode("utf-8")
        ).hexdigest()
        with transaction(ctx.conn):
            row, created = repo.insert_or_get(
                ctx.conn, notification_type=notification_type, priority=priority,
                fingerprint=fingerprint, payload=payload_json,
                not_before=_iso(eligible), expires_at=_iso(expiry), queued_at=_iso(queued_at),
            )
            if created:
                AuditService.record(
                    ctx, action=AuditAction.create, entity_type="notification_dispatch",
                    entity_id=row["id"], entity_ulid=row["ulid"],
                    after={
                        "notification_type": row["notification_type"],
                        "priority": row["priority"], "fingerprint": row["fingerprint"],
                        "not_before": row["not_before"], "expires_at": row["expires_at"],
                    },
                )
        return row

    @staticmethod
    def list_eligible(
        ctx: ServiceContext, *, now: datetime, limit: int = 50,
    ) -> list[dict[str, Any]]:
        instant = _aware(now, "now")
        if limit < 1 or limit > 500:
            raise ValidationError("limit must be between 1 and 500")
        return repo.list_eligible(ctx.conn, now=_iso(instant), limit=limit)

    @staticmethod
    def mark_sent(
        ctx: ServiceContext, ulid: str, *, sent_at: datetime,
    ) -> bool:
        instant = _aware(sent_at, "sent_at")
        with transaction(ctx.conn):
            row = repo.get_by_ulid(ctx.conn, ulid)
            if row is None:
                raise NotFoundError(f"notification dispatch not found: {ulid}")
            changed = repo.mark_sent(ctx.conn, ulid=ulid, sent_at=_iso(instant))
            if changed:
                AuditService.record(
                    ctx, action=AuditAction.update, entity_type="notification_dispatch",
                    entity_id=row["id"], entity_ulid=row["ulid"],
                    after={"sent_at": _iso(instant), "fingerprint": row["fingerprint"]},
                )
        return changed
