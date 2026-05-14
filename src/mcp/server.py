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

from ..auth import COOKIE_NAME, verify_bearer, verify_session_cookie
from . import tools as _tools  # noqa: F401 — imports register the tools
from .registry import mcp

log = logging.getLogger("artemide.mcp")


class BearerOrCookieAuthASGIMiddleware:
    """ASGI middleware enforcing the same auth model as the REST API."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._authorised(scope):
            await self.app(scope, receive, send)
            return

        await self._reject(scope, receive, send)

    @staticmethod
    def _authorised(scope: Scope) -> bool:
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1", errors="ignore")
        if auth.lower().startswith("bearer ") and verify_bearer(auth[7:]):
            return True
        raw_cookie = headers.get(b"cookie", b"").decode("latin-1", errors="ignore")
        if raw_cookie:
            jar = SimpleCookie()
            try:
                jar.load(raw_cookie)
            except Exception:
                return False
            morsel = jar.get(COOKIE_NAME)
            if morsel and verify_session_cookie(morsel.value):
                return True
        return False

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
