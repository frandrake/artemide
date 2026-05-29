"""Bearer-token and signed session-cookie authentication.

v1.2: a bearer token resolves to an `api_tokens` row carrying an actor and an
owner/bot role (Rule 18). Only the SHA-256 hash is ever stored. Cookie sessions
are always the owner ('FF'). Backward compatible: the pre-v1.2 single token
(env `ARTEMIDE_API_TOKEN` or the DB-stored rotated token) resolves to
owner 'FF'; `ARTEMIDE_N8N_TOKEN` resolves to the bot 'n8n_bot' for first boot.
"""
from __future__ import annotations

import contextvars
import hashlib
import hmac
import logging
import os
from typing import Final

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

log = logging.getLogger("artemide.auth")

COOKIE_NAME: Final[str] = "artemide_session"
SESSION_TTL_SECONDS: Final[int] = 7 * 24 * 3600
_ACTOR: Final[str] = "FF"
_BOT_ACTOR: Final[str] = "n8n_bot"

# Resolved (actor, role) for the current MCP request, set by the MCP ASGI
# middleware and read by tool_session. Defaults to owner for non-request
# contexts (seed scripts, tests, CLI).
current_auth: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar(
    "current_auth", default=(_ACTOR, "owner")
)


def _api_token() -> str:
    return os.environ.get("ARTEMIDE_API_TOKEN", "")


def _bot_env_token() -> str:
    return os.environ.get("ARTEMIDE_N8N_TOKEN", "")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _cookie_signer() -> TimestampSigner:
    secret = os.environ.get("ARTEMIDE_COOKIE_SECRET")
    if not secret:
        secret = _api_token() or "insecure-dev-default-change-me"
    return TimestampSigner(secret, salt="artemide-session")


def resolve_bearer(token: str) -> tuple[str, str] | None:
    """Resolve a bearer token to (actor, role), or None if invalid.

    Read-only: the persistent backfill happens once in ensure_seed_tokens().
    Includes an env fallback so first boot / tests work before the bootstrap.
    """
    if not token:
        return None
    token = token.strip()
    from .db import get_connection
    from .repository import api_tokens as tokens_repo

    try:
        conn = get_connection()
        try:
            row = tokens_repo.get_active_by_hash(conn, hash_token(token))
        finally:
            conn.close()
        if row is not None:
            return row.actor, row.role.value
    except Exception as e:  # pragma: no cover - defensive
        log.warning("api_tokens lookup failed: %s", e)

    # Fallback: the legacy owner token (DB-stored rotated token wins over env).
    from .services.system_service import get_active_api_token

    owner_token = get_active_api_token(_api_token())
    if owner_token and hmac.compare_digest(token, owner_token):
        return _ACTOR, "owner"
    bot_token = _bot_env_token()
    if bot_token and hmac.compare_digest(token, bot_token):
        return _BOT_ACTOR, "bot"
    return None


def verify_bearer(token: str) -> bool:
    """True if the token is any valid bearer (owner or bot)."""
    return resolve_bearer(token) is not None


def verify_owner_bearer(token: str) -> bool:
    """True only for an owner-role token (used by the cookie-login endpoint)."""
    resolved = resolve_bearer(token)
    return resolved is not None and resolved[1] == "owner"


def ensure_seed_tokens() -> None:
    """Register the active owner token and the first-boot bot token (env) into
    api_tokens if not already present. Idempotent; runs on app startup."""
    from .db import get_connection
    from .repository import api_tokens as tokens_repo
    from .services.system_service import get_active_api_token

    conn = get_connection()
    try:
        owner_token = get_active_api_token(_api_token())
        if owner_token:
            h = hash_token(owner_token)
            if tokens_repo.get_by_hash(conn, h) is None:
                tokens_repo.insert_token(conn, token_hash=h, actor=_ACTOR, role="owner")
                log.info("backfilled owner token into api_tokens (actor=%s)", _ACTOR)
        bot_token = _bot_env_token()
        if bot_token:
            h = hash_token(bot_token)
            if tokens_repo.get_by_hash(conn, h) is None:
                tokens_repo.insert_token(conn, token_hash=h, actor=_BOT_ACTOR, role="bot")
                log.info("registered first-boot bot token into api_tokens (actor=%s)", _BOT_ACTOR)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("ensure_seed_tokens failed: %s", e)
    finally:
        conn.close()


def create_session_cookie() -> str:
    return _cookie_signer().sign(_ACTOR).decode("ascii")


def verify_session_cookie(value: str | None) -> str | None:
    if not value:
        return None
    try:
        payload = _cookie_signer().unsign(value, max_age=SESSION_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return payload.decode("ascii") if isinstance(payload, (bytes, bytearray)) else str(payload)


def resolve_request_identity(request: Request) -> tuple[str, str] | None:
    """Return (actor, role) for a request, or None if unauthenticated.

    Bearer tokens carry their role; a valid cookie session is always owner.
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        resolved = resolve_bearer(auth_header[7:])
        if resolved is not None:
            return resolved
    cookie_value = request.cookies.get(COOKIE_NAME)
    actor = verify_session_cookie(cookie_value)
    if actor:
        return actor, "owner"
    return None


def auth_dependency(request: Request) -> tuple[str, str]:
    """FastAPI dependency. Returns (actor, role) or raises 401."""
    identity = resolve_request_identity(request)
    if identity is not None:
        request.state.actor, request.state.role = identity
        return identity
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
