"""Artemide FastAPI application."""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .api.deps import get_db
from .api.error_handlers import register_error_handlers
from .api.routes_admin import router as admin_router
from .api.routes_audit import router as audit_router
from .api.routes_contacts import router as contacts_router
from .api.routes_export import router as export_router
from .api.routes_firms import router as firms_router
from .api.routes_import import router as import_router
from .api.routes_notes import router as notes_router
from .api.routes_partners import router as partners_router
from .api.routes_planning import router as planning_router
from .api.routes_search import router as search_router
from .auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    create_session_cookie,
    verify_bearer,
)
from .db import init_db


log = logging.getLogger("artemide")
logging.basicConfig(level=os.environ.get("ARTEMIDE_LOG_LEVEL", "INFO"))


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("artemide ready")
    yield


_enable_docs = _truthy(os.environ.get("ARTEMIDE_ENABLE_DOCS"))

app = FastAPI(
    title="Artemide",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json" if _enable_docs else None,
    lifespan=lifespan,
)

register_error_handlers(app)

for router in (
    firms_router,
    partners_router,
    contacts_router,
    notes_router,
    planning_router,
    audit_router,
    search_router,
    export_router,
    import_router,
    admin_router,
):
    app.include_router(router)


# ---------- /health ----------

@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------- session login/logout ----------

class LoginInput(BaseModel):
    token: str


def _cookie_kwargs() -> dict:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": _truthy(os.environ.get("ARTEMIDE_COOKIE_SECURE", "true")),
        "samesite": "strict",
        "domain": os.environ.get("ARTEMIDE_COOKIE_DOMAIN") or None,
        "path": "/",
    }


@app.post("/login", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def login(body: LoginInput) -> Response:
    if not verify_bearer(body.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
        )
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.set_cookie(
        value=create_session_cookie(),
        max_age=SESSION_TTL_SECONDS,
        **_cookie_kwargs(),
    )
    return resp


@app.post("/logout", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def logout() -> Response:
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(**_cookie_kwargs())
    return resp


# ---------- optional docs ----------

if _enable_docs:

    @app.get("/api/v1/docs", include_in_schema=False)
    def swagger_ui():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="Artemide API — docs",
        )

    @app.get("/api/v1/redoc", include_in_schema=False)
    def redoc_ui():
        return get_redoc_html(openapi_url=app.openapi_url, title="Artemide API — ReDoc")


# ---------- FastMCP placeholder (Phase 4) ----------

try:
    from fastmcp import FastMCP

    _mcp = FastMCP("Artemide")
    try:
        _mcp_app = _mcp.http_app(path="/")
        app.mount("/mcp", _mcp_app)
    except Exception as mount_err:  # pragma: no cover — exercised in Phase 4
        log.warning("FastMCP mount deferred to Phase 4: %s", mount_err)
except Exception as import_err:  # pragma: no cover
    log.warning("FastMCP unavailable: %s", import_err)


# ---------- static UI (Phase 5+) ----------

_ui_path = Path(os.environ.get("ARTEMIDE_UI_BUILD_PATH", "/app/web/dist"))
if _ui_path.exists() and _ui_path.is_dir():
    app.mount("/", StaticFiles(directory=str(_ui_path), html=True), name="ui")
else:
    log.warning("UI build path %s not present; static mount skipped", _ui_path)


# ---------- entry point ----------

def main() -> None:
    uvicorn.run(
        "src.app:app",
        host=os.environ.get("ARTEMIDE_BIND_HOST", "0.0.0.0"),
        port=int(os.environ.get("ARTEMIDE_BIND_PORT", "8000")),
        log_level=os.environ.get("ARTEMIDE_LOG_LEVEL", "info").lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
