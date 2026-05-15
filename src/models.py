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
    draft = "draft"
    send = "send"
    template = "template"
    stage = "stage"


class OutreachChannel(str, Enum):
    email = "email"
    linkedin = "linkedin"
    message = "message"
    other = "other"


class DraftStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    sent = "sent"
    archived = "archived"


class OutreachStage(str, Enum):
    researched = "researched"
    drafted = "drafted"
    sent = "sent"
    replied = "replied"
    met = "met"
    ongoing = "ongoing"
    paused = "paused"
    dropped = "dropped"


class TemplateCategory(str, Enum):
    cold_intro = "cold_intro"
    warm_followup = "warm_followup"
    thought_share = "thought_share"
    reciprocity = "reciprocity"
    freeform = "freeform"


class EngagementStatus(str, Enum):
    not_set = "not_set"
    planned = "planned"
    in_progress = "in_progress"
    complete = "complete"


class AuditTransport(str, Enum):
    api = "api"
    rest = "rest"
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
    # Headhunter intelligence fields (migration 010)
    market_tier: str | None = None
    strategic_fit: str | None = None
    ned_practice_strength: str | None = None
    hq_address: str | None = None
    sectors: str | None = None
    cmo_practice_depth: str | None = None
    comp_transparency: str | None = None
    candidate_reputation: str | None = None
    b2b_fs_reputation: str | None = None


class PartnerRecord(_Base):
    id: int
    ulid: str
    firm_id: int
    name: str
    title: str | None = None
    practice: str | None = None
    seniority: str | None = None
    location: str | None = None
    introduced_via: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relationship_state: RelationshipState = RelationshipState.cold
    last_contact_date: date | None = None
    next_touch_date: date | None = None
    next_touch_topic: str | None = None
    notes_summary: str | None = None
    follow_ups_outstanding: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # Headhunter intelligence fields (migration 010)
    practice_focus: str | None = None
    strategic_relevance: str | None = None
    warm_intro_angle: str | None = None
    thought_leadership: str | None = None
    prior_career: str | None = None
    ned_gateway: int = 0
    # Outreach pipeline stage (migration 011)
    outreach_stage: OutreachStage = OutreachStage.researched


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


class FirmUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tier: FirmTier | None = None
    region: str | None = None
    relationship_state: RelationshipState | None = None
    notes: str | None = None
    # Headhunter intelligence fields (migration 010)
    market_tier: str | None = None
    strategic_fit: str | None = None
    ned_practice_strength: str | None = None
    hq_address: str | None = None
    sectors: str | None = None
    cmo_practice_depth: str | None = None
    comp_transparency: str | None = None
    candidate_reputation: str | None = None
    b2b_fs_reputation: str | None = None


class PartnerUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    practice: str | None = None
    seniority: str | None = None
    location: str | None = None
    introduced_via: str | None = None
    first_contact_date: date | None = None
    next_planned_touch_date: date | None = None
    next_planned_topic: str | None = None
    follow_ups_outstanding: list[str] | None = None
    # Headhunter intelligence fields (migration 010)
    practice_focus: str | None = None
    strategic_relevance: str | None = None
    warm_intro_angle: str | None = None
    thought_leadership: str | None = None
    prior_career: str | None = None
    ned_gateway: int | None = None
    # Outreach pipeline stage (migration 011)
    outreach_stage: OutreachStage | None = None


# ---------- engagement_calendar / templates / outreach records ----------

class EngagementCalendarRecord(_Base):
    id: int
    ulid: str
    firm_id: int | None = None
    partner_id: int | None = None
    due_date: date
    title: str
    description: str | None = None
    status: EngagementStatus = EngagementStatus.not_set
    track: str | None = None
    created_at: datetime


class TemplateRecord(_Base):
    id: int
    ulid: str
    name: str
    category: str | None = None
    channel: OutreachChannel
    subject_template: str | None = None
    body_template: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class OutreachDraftRecord(_Base):
    id: int
    ulid: str
    partner_id: int
    template_id: int | None = None
    channel: OutreachChannel
    subject: str | None = None
    body: str
    status: DraftStatus = DraftStatus.draft
    version: int = 1
    sent_message_id: int | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class OutreachDraftVersionRecord(_Base):
    id: int
    ulid: str
    draft_id: int
    version: int
    subject: str | None = None
    body: str
    author_actor: str
    created_at: datetime


class OutreachMessageRecord(_Base):
    id: int
    ulid: str
    draft_id: int
    partner_id: int
    contact_log_id: int
    sent_at: datetime
    sent_via: OutreachChannel
    recipient_handle: str | None = None
    subject_snapshot: str | None = None
    body_snapshot: str
    version_sent: int


# ---------- engagement_calendar / templates / outreach inputs ----------

class EngagementCalendarUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: EngagementStatus | None = None
    due_date: date | None = None
    title: str | None = None
    description: str | None = None
    track: str | None = None


class TemplateCreateInput(BaseModel):
    name: str
    channel: OutreachChannel
    body_template: str
    subject_template: str | None = None
    category: str | None = None
    description: str | None = None


class TemplateUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    channel: OutreachChannel | None = None
    subject_template: str | None = None
    body_template: str | None = None
    category: str | None = None
    description: str | None = None


class TemplateRenderInput(BaseModel):
    partner_ulid: str
    overrides: dict[str, str] | None = None


class OutreachDraftCreateInput(BaseModel):
    partner_ulid: str
    channel: OutreachChannel
    subject: str | None = None
    body: str = ""  # empty + template_ulid → server renders
    template_ulid: str | None = None
    status: DraftStatus = DraftStatus.draft


class OutreachDraftUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str | None = None
    body: str | None = None
    channel: OutreachChannel | None = None
    status: DraftStatus | None = None  # 'sent' is rejected here — must use send endpoint
    template_ulid: str | None = None


class OutreachSendInput(BaseModel):
    draft_ulid: str
    sent_at: datetime | None = None
    sent_via: OutreachChannel | None = None
    recipient_handle: str | None = None
    initiated_by: InitiatedBy = InitiatedBy.me
    contact_summary: str | None = None


class PipelineFilterInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tier: FirmTier | None = None
    strategic_relevance: str | None = None
    ned_gateway: bool | None = None
    track: str | None = None
