"""BoardInteractionsService — the board activity log (polymorphic link).

Owner-only; no outbox, no shared search index. An interaction linked to an
opportunity also lands on that opportunity's timeline (board_opportunity_log).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..api._serde import to_response
from ..models import (
    AuditAction,
    BoardInteractionRecord,
    BoardLinkedEntityType,
    BoardOppEventType,
    LogBoardInteractionInput,
)
from ..repository import board_contacts as contacts_repo
from ..repository import board_firms as firms_repo
from ..repository import board_interactions as interactions_repo
from ..repository import board_opportunities as opportunities_repo
from . import ServiceContext, assert_owner, transaction
from .audit_service import AuditService
from .exceptions import NotFoundError


class BoardInteractionsService:

    @staticmethod
    def _validate_linked(ctx: ServiceContext, entity_type: BoardLinkedEntityType, ulid: str):
        if entity_type == BoardLinkedEntityType.board_firm:
            ent = firms_repo.get_firm_by_ulid(ctx.conn, ulid)
        elif entity_type == BoardLinkedEntityType.board_contact:
            ent = contacts_repo.get_contact_by_ulid(ctx.conn, ulid)
        else:
            ent = opportunities_repo.get_opportunity_by_ulid(ctx.conn, ulid)
        if ent is None:
            raise NotFoundError(f"{entity_type.value} not found: {ulid}")
        return ent

    @staticmethod
    def log_interaction(ctx: ServiceContext, data: LogBoardInteractionInput) -> BoardInteractionRecord:
        assert_owner(ctx, operation="log board interaction")
        with transaction(ctx.conn):
            linked = BoardInteractionsService._validate_linked(
                ctx, data.linked_entity_type, data.linked_entity_ulid
            )
            interaction = interactions_repo.insert_interaction(
                ctx.conn,
                interaction_date=data.interaction_date or date.today(),
                interaction_type=data.interaction_type,
                linked_entity_type=data.linked_entity_type,
                linked_entity_ulid=data.linked_entity_ulid,
                summary=data.summary,
                next_action=data.next_action,
                due_date=data.due_date,
            )
            # Mirror onto the opportunity timeline when linked to one.
            if data.linked_entity_type == BoardLinkedEntityType.board_opportunity:
                opportunities_repo.insert_log(
                    ctx.conn, opportunity_id=linked.id,
                    event_date=data.interaction_date or date.today(),
                    event_type=BoardOppEventType.interaction,
                    summary=data.summary or data.interaction_type.value,
                )
            AuditService.record(
                ctx, action=AuditAction.create, entity_type="board_interaction",
                entity_id=interaction.id, entity_ulid=interaction.ulid,
                after={
                    "linked_entity_type": data.linked_entity_type.value,
                    "linked_entity_ulid": data.linked_entity_ulid,
                    "interaction_type": data.interaction_type.value,
                },
            )
            return interaction

    @staticmethod
    def list_for_entity(
        ctx: ServiceContext, entity_type: BoardLinkedEntityType, entity_ulid: str
    ) -> list[BoardInteractionRecord]:
        assert_owner(ctx, operation="list board interactions")
        return interactions_repo.list_by_entity(ctx.conn, entity_type, entity_ulid)

    @staticmethod
    def list_due(ctx: ServiceContext, *, within_days: int = 14) -> list[dict[str, Any]]:
        """Interactions with a due_date on or before today + within_days."""
        assert_owner(ctx, operation="list board interactions due")
        cutoff = date.today() + timedelta(days=max(0, within_days))
        return [to_response(i) for i in interactions_repo.list_due(ctx.conn, due_on_or_before=cutoff)]
