"""Bearer-token and signed session-cookie authentication."""
from __future__ import annotations

import hmac
import os
import time
from typing import Final

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner


COOKIE_NAME: Final[str] = "artemide_session"
SESSION_TTL_SECONDS: Final[int] = 7 * 24 * 3600
_ACTOR: Final[str] = "FF"


def _api_token() -> str:
    return os.environ.get("ARTEMIDE_API_TOKEN", "")


def _cookie_signer() -> TimestampSigner:
    secret = os.environ.get("ARTEMIDE_COOKIE_SECRET")
    if not secret:
        secret = _api_token() or "insecure-dev-default-change-me"
    return TimestampSigner(secret, salt="artemide-session")


def verify_bearer(token: str) -> bool:
    # The DB-stored token (set by /api/v1/admin/rotate-token) takes
    # precedence over the env var so a rotated token works without a
    # process restart, and the old env value is no longer accepted.
    from .services.system_service import get_active_api_token

    expected = get_active_api_token(_api_token())
    if not expected or not token:
        return False
    return hmac.compare_digest(token.strip(), expected)


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


def auth_dependency(request: Request) -> str:
    """FastAPI dependency. Returns actor name or raises 401."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        if verify_bearer(auth_header[7:]):
            return _ACTOR
    cookie_value = request.cookies.get(COOKIE_NAME)
    actor = verify_session_cookie(cookie_value)
    if actor:
        return actor
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
