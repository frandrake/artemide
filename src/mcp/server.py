"""FastMCP server mounted at /mcp.

Registers all tools, wraps the ASGI app in a bearer/cookie auth
middleware so every MCP request is authenticated identically to REST.
"""
from __future__ import annotations

import json
import logging
from http.cookies import SimpleCookie
from typing import Awaitable, Callable

from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ..auth import COOKIE_NAME, current_auth, resolve_bearer, verify_session_cookie
from . import tools as _tools  # noqa: F401 — imports register the tools
from .registry import mcp

log = logging.getLogger("artemide.mcp")


class BearerOrCookieAuthASGIMiddleware:
    """ASGI middleware enforcing the same auth model as the REST API.

    On success it stashes the resolved (actor, role) in the `current_auth`
    contextvar so tool_session threads the correct role into ServiceContext
    (Rule 18 — e.g. approve_message is owner-only).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        identity = self._identity(scope)
        if identity is not None:
            token = current_auth.set(identity)
            try:
                await self.app(scope, receive, send)
            finally:
                current_auth.reset(token)
            return

        await self._reject(scope, receive, send)

    @staticmethod
    def _identity(scope: Scope) -> tuple[str, str] | None:
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1", errors="ignore")
        if auth.lower().startswith("bearer "):
            resolved = resolve_bearer(auth[7:])
            if resolved is not None:
                return resolved
        raw_cookie = headers.get(b"cookie", b"").decode("latin-1", errors="ignore")
        if raw_cookie:
            jar = SimpleCookie()
            try:
                jar.load(raw_cookie)
            except Exception:
                return None
            morsel = jar.get(COOKIE_NAME)
            if morsel and verify_session_cookie(morsel.value):
                return "FF", "owner"
        return None

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        body = json.dumps({"error": "unauthorized"}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b'Bearer realm="artemide"'),
            ],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})


def get_mcp_app() -> ASGIApp:
    """Return the auth-wrapped ASGI sub-app for mounting in FastAPI."""
    return mcp.http_app(
        path="/",
        middleware=[Middleware(BearerOrCookieAuthASGIMiddleware)],
        stateless_http=True,
    )
