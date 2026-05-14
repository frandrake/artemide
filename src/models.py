"""Pydantic models for Artemide entities and tool/API inputs."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------- enums ----------

class FirmTier(str, Enum):
    primary = "primary"
    specialist = "specialist"
    ned = "ned"


class RelationshipState(str, Enum):
    warm = "warm"
    warming = "warming"
    cold = "cold"
    dormant = "dormant"


class ContactChannel(str, Enum):
    email = "email"
    call = "call"
    coffee = "coffee"
    event = "event"
    inmail = "inmail"
    message = "message"
    other = "other"


class InitiatedBy(str, Enum):
    me = "me"
    them = "them"


class NoteEntityType(str, Enum):
    firm = "firm"
    partner = "partner"


class CalendarStatus(str, Enum):
    not_set = "not_set"
    planned = "planned"
    in_progress = "in_progress"
    complete = "complete"


class AuditAction(str, Enum):
    create = "create"
    update = "update"
    delete = "delete"
    restore = "restore"
    log_contact = "log_contact"
    import_ = "import"
    note = "note"
    plan = "plan"
    rotate_token = "rotate_token"


class AuditTransport(str, Enum):
    api = "api"
    mcp = "mcp"
    web = "web"
    cli = "cli"
    system = "system"


# ---------- record models ----------

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FirmRecord(_Base):
    id: int
    ulid: str
    name: str
    tier: FirmTier
    region: str | None = None
    relationship_state: RelationshipState = RelationshipState.cold
    primary_focus: str | None = None
    notes_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class PartnerRecord(_Base):
    id: int
    ulid: str
    firm_id: int
    name: str
    title: str | None = None
    practice: str | None = None
    seniority: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relationship_state: RelationshipState = RelationshipState.cold
    last_contact_date: date | None = None
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    notes_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ContactLogRecord(_Base):
    id: int
    ulid: str
    partner_id: int
    contact_date: date
    channel: ContactChannel
    initiated_by: InitiatedBy
    summary: str | None = None
    value_given: str | None = None
    value_received: str | None = None
    follow_up: str | None = None
    created_at: datetime


class NoteRecord(_Base):
    id: int
    ulid: str
    entity_type: NoteEntityType
    entity_id: str
    body: str
    created_at: datetime


class ValueCalendarRecord(_Base):
    id: int
    ulid: str
    year: int
    quarter: int
    topic: str | None = None
    status: CalendarStatus = CalendarStatus.not_set
    created_at: datetime
    updated_at: datetime


class AuditLogRecord(_Base):
    id: int
    ulid: str
    entity_type: str
    entity_id: str
    action: AuditAction
    actor: str
    transport: AuditTransport
    payload: str | None = None
    timestamp: datetime


# ---------- tool / API input models ----------

class LogContactInput(BaseModel):
    partner_ulid: str
    contact_date: date
    channel: ContactChannel
    initiated_by: InitiatedBy
    summary: str | None = None
    value_given: str | None = None
    value_received: str | None = None
    follow_up: str | None = None


class UpsertPartnerInput(BaseModel):
    firm_ulid: str
    name: str
    title: str | None = None
    practice: str | None = None
    seniority: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relationship_state: RelationshipState | None = None
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    notes_summary: str | None = None


class GetPartnerStateInput(BaseModel):
    partner_ulid: str


class ListDueTouchesInput(BaseModel):
    window_days: int = Field(default=14, ge=0)
    tier: FirmTier | None = None


class PlanQuarterInput(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)


class SetQuarterTopicInput(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)
    topic: str
    status: CalendarStatus | None = None


class ImportMarkdownInput(BaseModel):
    body: str
    source: str | None = None


class CreateNoteInput(BaseModel):
    entity_type: NoteEntityType
    entity_ulid: str
    body: str


class SearchInput(BaseModel):
    query: str
    entity_type: str | None = None
    limit: int = Field(default=20, ge=1, le=200)
