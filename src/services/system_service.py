"""System config service — currently just the API token."""
from __future__ import annotations

import logging
import secrets
import sqlite3

from ..db import get_connection
from ..models import AuditAction, AuditTransport
from ..repository import audit_log as audit_repo
from . import ServiceContext

log = logging.getLogger("artemide.system")
API_TOKEN_KEY = "api_token"


def get_config(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM system_config WHERE key = ?", (key,)
    ).fetchone()
    return None if row is None else str(row[0])


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO system_config (key, value, updated_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP) "
        "ON CONFLICT(key) DO UPDATE SET "
        "value = excluded.value, updated_at = CURRENT_TIMESTAMP",
        (key, value),
    )


def get_active_api_token(env_default: str) -> str:
    """Returns the live API token. DB-stored value wins if present."""
    try:
        conn = get_connection()
        try:
            value = get_config(conn, API_TOKEN_KEY)
        finally:
            conn.close()
    except Exception as e:
        log.warning("system_config lookup failed: %s", e)
        value = None
    return value or env_default


class SystemService:

    @staticmethod
    def rotate_api_token(ctx: ServiceContext) -> str:
        from ..auth import hash_token
        from ..repository import api_tokens as tokens_repo

        new_token = secrets.token_hex(32)
        set_config(ctx.conn, API_TOKEN_KEY, new_token)
        # v1.2: keep api_tokens in step — retire prior owner tokens, register
        # the new one, so the old bearer is rejected at the auth layer.
        tokens_repo.deactivate_by_role(ctx.conn, "owner")
        tokens_repo.insert_token(
            ctx.conn, token_hash=hash_token(new_token), actor=ctx.actor or "FF", role="owner"
        )
        audit_repo.insert_audit_entry(
            ctx.conn,
            entity_type="system_config",
            entity_id=API_TOKEN_KEY,
            action=AuditAction.rotate_token,
            actor=ctx.actor,
            transport=AuditTransport(ctx.transport)
            if not isinstance(ctx.transport, AuditTransport)
            else ctx.transport,
            payload=None,
        )
        return new_token

    @staticmethod
    def issue_bot_token(ctx: ServiceContext, *, actor: str = "n8n_bot") -> str:
        """Issue a fresh bot-role token (Settings → Automation). Retires prior
        bot tokens; returns the plaintext once. Owner-gated by the caller."""
        from ..auth import hash_token
        from ..repository import api_tokens as tokens_repo

        new_token = secrets.token_hex(32)
        tokens_repo.deactivate_by_role(ctx.conn, "bot")
        tokens_repo.insert_token(
            ctx.conn, token_hash=hash_token(new_token), actor=actor, role="bot"
        )
        audit_repo.insert_audit_entry(
            ctx.conn,
            entity_type="api_token",
            entity_id=actor,
            action=AuditAction.rotate_token,
            actor=ctx.actor,
            transport=AuditTransport(ctx.transport)
            if not isinstance(ctx.transport, AuditTransport)
            else ctx.transport,
            payload=None,
        )
        return new_token

    @staticmethod
    def has_db_token(conn: sqlite3.Connection) -> bool:
        return get_config(conn, API_TOKEN_KEY) is not None
