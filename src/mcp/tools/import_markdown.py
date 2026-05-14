"""Import a markdown ledger (idempotent)."""
from __future__ import annotations

from dataclasses import asdict

from ...models import ImportMarkdownInput
from ...services.import_service import ImportService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def import_markdown(payload: ImportMarkdownInput) -> dict:
    """Ingest a markdown ledger; duplicates are skipped via Rule 5."""
    with tool_session("import_markdown") as (_, ctx):
        try:
            summary = ImportService.import_markdown(ctx, payload.body)
            return {"ok": True, "summary": asdict(summary)}
        except Exception as e:
            return error_response(e)
