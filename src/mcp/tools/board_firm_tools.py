"""MCP tools — board firms & contacts (owner-only; bot tokens get forbidden_role)."""
from __future__ import annotations

from ...api._serde import to_response
from ...models import (
    BoardFirmStatus,
    BoardRelationship,
    UpsertBoardContactInput,
    UpsertBoardFirmInput,
)
from ...services.board_contacts_service import BoardContactsService
from ...services.board_firms_service import BoardFirmsService
from .._common import error_response, tool_session
from ..registry import mcp


@mcp.tool
def board_upsert_firm(payload: UpsertBoardFirmInput) -> dict:
    """Create or update a board search firm/platform (matched by ulid or name)."""
    with tool_session("board_upsert_firm") as (conn, ctx):
        try:
            f = BoardFirmsService.upsert(ctx, payload)
            return {"ok": True, "firm": BoardFirmsService.to_payload(f)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_list_firms(status: BoardFirmStatus | None = None, tier: int | None = None) -> dict:
    """List board firms, optionally filtered by status/tier (grouped by tier in the UI)."""
    with tool_session("board_list_firms") as (conn, ctx):
        try:
            items = BoardFirmsService.list(ctx, status=status, tier=tier)
            return {"ok": True, "firms": [BoardFirmsService.to_payload(f) for f in items]}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_get_firm(firm_ulid: str) -> dict:
    """Get a board firm with its contacts."""
    with tool_session("board_get_firm") as (conn, ctx):
        try:
            f = BoardFirmsService.get_by_ulid(ctx, firm_ulid)
            payload = BoardFirmsService.to_payload(f)
            payload["contacts"] = [
                BoardContactsService.to_payload(ctx, c)
                for c in BoardContactsService.list(ctx, firm_ulid=f.ulid)
            ]
            return {"ok": True, "firm": payload}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_upsert_contact(payload: UpsertBoardContactInput) -> dict:
    """Create or update a board contact (partner, chair, connector)."""
    with tool_session("board_upsert_contact") as (conn, ctx):
        try:
            c = BoardContactsService.upsert(ctx, payload)
            return {"ok": True, "contact": BoardContactsService.to_payload(ctx, c)}
        except Exception as e:
            return error_response(e)


@mcp.tool
def board_list_contacts(
    firm_ulid: str | None = None,
    relationship: BoardRelationship | None = None,
    stale: bool = False,
) -> dict:
    """List board contacts; stale=true returns only those flagged verify_before_send (R5)."""
    with tool_session("board_list_contacts") as (conn, ctx):
        try:
            items = BoardContactsService.list(
                ctx, firm_ulid=firm_ulid, relationship=relationship, stale_only=stale
            )
            return {"ok": True, "contacts": [BoardContactsService.to_payload(ctx, c) for c in items]}
        except Exception as e:
            return error_response(e)
