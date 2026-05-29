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
from .api.routes_analytics import router as analytics_router
from .api.routes_audit import router as audit_router
from .api.routes_contacts import router as contacts_router
from .api.routes_engagement import router as engagement_router
from .api.routes_engagements import router as engagements_router
from .api.routes_events import router as events_router
from .api.routes_export import router as export_router
from .api.routes_firms import router as firms_router
from .api.routes_fit import router as fit_router
from .api.routes_import import router as import_router
from .api.routes_messages import router as messages_router
from .api.routes_notes import router as notes_router
from .api.routes_orgs import router as orgs_router
from .api.routes_outreach import router as outreach_router
from .api.routes_partners import router as partners_router
from .api.routes_pipeline import router as pipeline_router
from .api.routes_planning import router as planning_router
from .api.routes_programme import router as programme_router
from .api.routes_search import router as search_router
from .api.routes_system import router as system_router
from .api.routes_templates import router as templates_router
from .auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    create_session_cookie,
    ensure_seed_tokens,
    verify_owner_bearer,
)
from .db import init_db
from .mcp.server import get_mcp_app


log = logging.getLogger("artemide")
logging.basicConfig(level=os.environ.get("ARTEMIDE_LOG_LEVEL", "INFO"))


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


_mcp_app = get_mcp_app()


async def _outbox_sweep_loop() -> None:
    """In-process periodic outbox sweep (Rule 19). No external scheduler, no
    inbound ports. Best-effort: a sweep failure never tears down the app."""
    import asyncio

    from .db import get_connection
    from .services.outbox_service import OutboxService

    try:
        interval = int(os.environ.get("ARTEMIDE_OUTBOX_SWEEP_INTERVAL", "300"))
    except ValueError:
        interval = 300
    while True:
        await asyncio.sleep(max(30, interval))
        try:
            conn = get_connection()
            try:
                OutboxService.sweep(conn)
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("outbox sweep failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    init_db()
    ensure_seed_tokens()
    log.info("artemide ready")
    sweep_task = None
    if _truthy(os.environ.get("ARTEMIDE_OUTBOX_ENABLED", "true")):
        sweep_task = asyncio.create_task(_outbox_sweep_loop())
    # Nest FastMCP's lifespan so its session manager starts/stops with us.
    try:
        async with _mcp_app.router.lifespan_context(app):
            yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()


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
    engagement_router,
    templates_router,
    outreach_router,
    pipeline_router,
    analytics_router,
    audit_router,
    search_router,
    export_router,
    import_router,
    admin_router,
    system_router,
    # v1.2 — engagement & programme extension
    orgs_router,
    engagements_router,
    fit_router,
    messages_router,
    programme_router,
    events_router,
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
    if not verify_owner_bearer(body.token):
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


# ---------- FastMCP ----------
# The ASGI sub-app was created earlier so its lifespan can be nested in
# the FastAPI lifespan.
app.mount("/mcp", _mcp_app)


# ---------- SPA fallback routes for dynamic detail pages ----------
# Astro builds /firm-detail/index.html and /partner-detail/index.html as
# shell pages. We don't know firm/partner ULIDs at build time, so we
# serve those shells in response to /firms/{ulid} and /partners/{ulid}.
# Each shell's React island reads the ULID from window.location.pathname.

from fastapi.responses import FileResponse  # noqa: E402

_ui_path = Path(os.environ.get("ARTEMIDE_UI_BUILD_PATH", "/app/web/dist"))


def _serve_detail_shell(name: str) -> FileResponse:
    p = _ui_path / name / "index.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="ui shell missing")
    return FileResponse(str(p), media_type="text/html")


@app.get("/firms/{ulid}", include_in_schema=False)
def _firm_detail_shell(ulid: str):
    if not ulid or ulid == "index" or "/" in ulid:
        raise HTTPException(status_code=404)
    return _serve_detail_shell("firm-detail")


@app.get("/partners/{ulid}", include_in_schema=False)
def _partner_detail_shell(ulid: str):
    if not ulid or ulid == "index" or "/" in ulid:
        raise HTTPException(status_code=404)
    return _serve_detail_shell("partner-detail")


# ---------- static UI (Phase 5+) ----------
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
