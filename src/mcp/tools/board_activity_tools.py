"""MCP tools — board competitors (R4), interactions, tasks, due, import/export."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import (
    BoardTaskStatus,
    ImportBoardMarkdownInput,
    LogBoardInteractionInput,
    UpsertBoardCompetitorInput,
    UpsertBoardTaskInput,
)
from ...services.board_competitors_service import BoardCompetitorsService
from ...services.board_export_service import BoardExportService
from ...services.board_import_service import BoardImportService
from ...services.board_interactions_service import BoardInteractionsService
from ...services.board_tasks_service import BoardTasksService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def board_list_competitors(active_only: bool = False) -> dict:
    """List the editable S&P competitor reference names (R4)."""
    with tool_session("board_list_competitors") as (conn, ctx):
        try:
            items = BoardCompetitorsService.list(ctx, active_only=active_only)
            return {"ok": True, "competitors": [BoardCompetitorsService.to_payload(c) for c in items]}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_upsert_competitor(payload: UpsertBoardCompetitorInput) -> dict:
    """Add or update an S&P competitor name in the reference list (R4)."""
    with tool_session("board_upsert_competitor") as (conn, ctx):
        try:
            c = BoardCompetitorsService.upsert(ctx, payload)
            return {"ok": True, "competitor": BoardCompetitorsService.to_payload(c)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_log_interaction(payload: LogBoardInteractionInput) -> dict:
    """Log a board interaction (email/call/meeting/...) against a firm, contact or opportunity."""
    with tool_session("board_log_interaction") as (conn, ctx):
        try:
            i = BoardInteractionsService.log_interaction(ctx, payload)
            return {"ok": True, "interaction": to_response(i)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_upsert_task(payload: UpsertBoardTaskInput) -> dict:
    """Create or update a board-domain task/reminder."""
    with tool_session("board_upsert_task") as (conn, ctx):
        try:
            t = BoardTasksService.upsert(ctx, payload)
            return {"ok": True, "task": BoardTasksService.to_payload(t)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_list_tasks(status: BoardTaskStatus | None = None, due_within_days: int | None = None) -> dict:
    """List board tasks, optionally by status / due window."""
    with tool_session("board_list_tasks") as (conn, ctx):
        try:
            items = BoardTasksService.list(ctx, status=status, due_within_days=due_within_days)
            return {"ok": True, "tasks": [BoardTasksService.to_payload(t) for t in items]}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_due(within_days: int = 14) -> dict:
    """Outreach due (board domain): interactions and open tasks with a due_date within the window."""
    with tool_session("board_due") as (conn, ctx):
        try:
            interactions = BoardInteractionsService.list_due(ctx, within_days=within_days)
            tasks = [
                BoardTasksService.to_payload(t)
                for t in BoardTasksService.list(ctx, status="open", due_within_days=within_days)
            ]
            return {"ok": True, "interactions": interactions, "tasks": tasks}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_import_markdown(payload: ImportBoardMarkdownInput) -> dict:
    """Seed the board ledger (tiered firms/contacts) from markdown; idempotent."""
    with tool_session("board_import_markdown") as (conn, ctx):
        try:
            from dataclasses import asdict

            summary = BoardImportService.import_markdown(ctx, payload.body)
            return {"ok": True, "summary": asdict(summary)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_export(format: str = "markdown", entity_type: str | None = None) -> dict:
    """Export the board domain. format='markdown' (full ledger) or 'csv' with
    entity_type in board_firm|board_contact|board_opportunity|board_evaluation."""
    with tool_session("board_export") as (conn, ctx):
        try:
            if format == "csv":
                if entity_type is None:
                    return {"ok": False, "error": "validation_error", "message": "entity_type required for csv"}
                return {"ok": True, "format": "csv", "content": BoardExportService.export_to_csv(ctx, entity_type)}
            return {"ok": True, "format": "markdown", "content": BoardExportService.export_to_markdown(ctx)}
        except Exception as e:
            return error_response(e)
