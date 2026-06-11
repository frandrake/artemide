"""Pydantic models for Artemide entities and tool/API inputs."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    org = "org"
    engagement = "engagement"


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
    # v1.2 — engagement & programme extension
    approve = "approve"
    ack = "ack"
    denied = "denied"
    # v1.3 — documents & interview transcripts
    attach = "attach"
    interview = "interview"


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


# ============================================================================
# v1.2 — engagement & programme extension
# ============================================================================

# ---------- v1.2 enums ----------

class ScaleBand(str, Enum):
    fortune_500 = "fortune_500"
    global_equivalent = "global_equivalent"
    pe_backed = "pe_backed"
    other = "other"


class WatchState(str, Enum):
    watch = "watch"
    target = "target"
    active = "active"
    parked = "parked"
    excluded = "excluded"


class RoleType(str, Enum):
    cmo = "cmo"
    cmgo = "cmgo"
    cco = "cco"
    transformation = "transformation"
    ned = "ned"
    other = "other"


class EngagementSource(str, Enum):
    inbound_partner = "inbound_partner"
    radar = "radar"
    referral = "referral"
    direct = "direct"
    flywheel = "flywheel"
    other = "other"


class EngagementStage(str, Enum):
    surfaced = "surfaced"
    exploratory = "exploratory"
    formal = "formal"
    final = "final"
    offer = "offer"
    decision = "decision"
    closed = "closed"


class EngagementInterest(str, Enum):
    pass_ = "pass"
    exploratory = "exploratory"
    active = "active"
    preferred = "preferred"


class ClosedReason(str, Enum):
    withdrew = "withdrew"
    rejected = "rejected"
    declined_offer = "declined_offer"
    accepted = "accepted"
    lapsed = "lapsed"


class EngagementEventType(str, Enum):
    stage_change = "stage_change"
    interview = "interview"
    reference = "reference"
    offer = "offer"
    note = "note"
    withdrawal = "withdrawal"


class MessageKind(str, Enum):
    inbound_reply = "inbound_reply"
    cadence_touch = "cadence_touch"
    cold_outreach = "cold_outreach"
    thank_you = "thank_you"
    custom = "custom"


class MessageChannel(str, Enum):
    email = "email"
    inmail = "inmail"
    message = "message"


class MessageStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    edited = "edited"
    sent = "sent"
    discarded = "discarded"


class MilestonePhase(str, Enum):
    build = "build"
    seed = "seed"
    run = "run"
    close = "close"
    exit = "exit"


class MilestoneStatus(str, Enum):
    pending = "pending"
    on_track = "on_track"
    at_risk = "at_risk"
    done = "done"


class TokenRole(str, Enum):
    owner = "owner"
    bot = "bot"


class RagStatus(str, Enum):
    green = "green"
    amber = "amber"
    red = "red"


# Stage progression order (Rule 14). 'closed' is reachable from any stage.
ENGAGEMENT_STAGE_ORDER: list[str] = [
    "surfaced", "exploratory", "formal", "final", "offer", "decision",
]


# ---------- v1.2 record models ----------

class OrganisationRecord(_Base):
    id: int
    ulid: str
    name: str
    sector: str | None = None
    scale_band: ScaleBand | None = None
    hq_region: str | None = None
    pertinence_note: str | None = None
    watch_state: WatchState = WatchState.watch
    source: str | None = None
    external_refs: str | None = None  # JSON: {capiq_id, website, linkedin}
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class EngagementRecord(_Base):
    id: int
    ulid: str
    org_id: int
    role_title: str
    role_type: RoleType | None = None
    source: EngagementSource | None = None
    source_partner_id: int | None = None
    stage: EngagementStage = EngagementStage.surfaced
    interest: EngagementInterest = EngagementInterest.exploratory
    comp_base_gbp: int | None = None
    comp_total_gbp: int | None = None
    comp_equity_note: str | None = None
    fit_score: int | None = None
    fit_breakdown: str | None = None  # JSON per-dimension scores + hard-filter result
    next_step: str | None = None
    next_step_date: date | None = None
    closed_reason: ClosedReason | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class EngagementLogRecord(_Base):
    id: int
    ulid: str
    engagement_id: int
    event_date: date
    event_type: EngagementEventType
    from_stage: str | None = None
    to_stage: str | None = None
    summary: str | None = None
    created_at: datetime


class EngagementProfileRecord(_Base):
    id: int
    ulid: str
    version: int
    active: int = 0
    comp_base_floor_gbp: int
    comp_total_target_gbp: int
    accepted_role_types: list[str]
    accepted_scale_bands: list[str]
    hard_exclusions: list[str]
    weights: dict[str, int]
    created_at: datetime

    @field_validator("accepted_role_types", "accepted_scale_bands", "hard_exclusions", "weights", mode="before")
    @classmethod
    def _parse_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class MessageRecord(_Base):
    id: int
    ulid: str
    kind: MessageKind | None = None
    partner_id: int | None = None
    engagement_id: int | None = None
    channel: MessageChannel | None = None
    recipient_hint: str | None = None
    subject: str | None = None
    body: str
    rationale: str | None = None
    status: MessageStatus = MessageStatus.proposed
    source_ref: str | None = None
    created_by_transport: str | None = None
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EventOutboxRecord(_Base):
    id: int
    ulid: str
    event_type: str
    entity_type: str
    entity_ulid: str
    payload: str | None = None
    created_at: datetime
    delivered_at: datetime | None = None
    delivery_attempts: int = 0


class ProgrammeMilestoneRecord(_Base):
    id: int
    ulid: str
    phase: MilestonePhase | None = None
    label: str
    target_date: date
    status: MilestoneStatus = MilestoneStatus.pending
    metric_note: str | None = None
    created_at: datetime
    updated_at: datetime


class ApiTokenRecord(_Base):
    id: int
    ulid: str
    token_hash: str
    actor: str
    role: TokenRole
    active: int = 1
    created_at: datetime
    rotated_at: datetime | None = None


# ---------- v1.2 input models ----------

class UpsertOrgInput(BaseModel):
    ulid: str | None = None
    name: str
    sector: str | None = None
    scale_band: ScaleBand | None = None
    hq_region: str | None = None
    pertinence_note: str | None = None
    watch_state: WatchState | None = None
    source: str | None = None
    external_refs: dict[str, Any] | None = None


class OrgUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    sector: str | None = None
    scale_band: ScaleBand | None = None
    hq_region: str | None = None
    pertinence_note: str | None = None
    watch_state: WatchState | None = None
    source: str | None = None
    external_refs: dict[str, Any] | None = None


class UpsertEngagementInput(BaseModel):
    ulid: str | None = None
    org_ulid: str
    role_title: str
    role_type: RoleType | None = None
    source: EngagementSource | None = None
    source_partner_ulid: str | None = None
    stage: EngagementStage | None = None
    interest: EngagementInterest | None = None
    comp_base_gbp: int | None = None
    comp_total_gbp: int | None = None
    comp_equity_note: str | None = None
    next_step: str | None = None
    next_step_date: date | None = None
    # tags used by the fit hard-filter (not persisted as a column; folded into
    # fit_breakdown evaluation). Optional free-form list.
    tags: list[str] | None = None


class EngagementUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role_title: str | None = None
    role_type: RoleType | None = None
    source: EngagementSource | None = None
    interest: EngagementInterest | None = None
    comp_base_gbp: int | None = None
    comp_total_gbp: int | None = None
    comp_equity_note: str | None = None
    next_step: str | None = None
    next_step_date: date | None = None


class AdvanceStageInput(BaseModel):
    to_stage: EngagementStage
    summary: str | None = None
    # Required only when to_stage == closed: closing is routed through the
    # single close() path so closed_reason is never left NULL (Rule 14).
    closed_reason: ClosedReason | None = None


class CloseEngagementInput(BaseModel):
    closed_reason: ClosedReason
    summary: str | None = None


class SetInterestInput(BaseModel):
    interest: EngagementInterest


class FitProfileInput(BaseModel):
    comp_base_floor_gbp: int
    comp_total_target_gbp: int
    accepted_role_types: list[str]
    accepted_scale_bands: list[str]
    hard_exclusions: list[str]
    weights: dict[str, int]

    @field_validator("weights")
    @classmethod
    def _weights_must_be_positive_sum(cls, v: dict[str, int]) -> dict[str, int]:
        if not v:
            raise ValueError("weights must not be empty")
        if any(w < 0 for w in v.values()):
            raise ValueError("weights must be non-negative")
        if sum(v.values()) <= 0:
            raise ValueError("weights must sum to a positive total")
        return v


class ProposeMessageInput(BaseModel):
    kind: MessageKind | None = None
    partner_ulid: str | None = None
    engagement_ulid: str | None = None
    channel: MessageChannel | None = None
    recipient_hint: str | None = None
    subject: str | None = None
    body: str
    rationale: str | None = None
    source_ref: str | None = None


class MessageEditInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str | None = None
    body: str | None = None


class UpsertMilestoneInput(BaseModel):
    ulid: str | None = None
    phase: MilestonePhase
    label: str
    target_date: date
    status: MilestoneStatus | None = None
    metric_note: str | None = None


class MilestoneUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str | None = None
    target_date: date | None = None
    status: MilestoneStatus | None = None
    metric_note: str | None = None


# ---------- v1.2 response / computed models ----------

class FitResult(BaseModel):
    score: int
    hard_fail: bool
    breakdown: dict[str, Any]


class ProgrammePhaseStatus(BaseModel):
    phase: str
    rag: RagStatus
    detail: str


class ProgrammeStatusResponse(BaseModel):
    days_to_target: int
    target_date: date
    overall_rag: RagStatus
    target_at_risk: bool
    phases: list[ProgrammePhaseStatus]


class OutboxHealth(BaseModel):
    undelivered: int
    oldest_undelivered_age_seconds: int | None = None
    past_attempt_cap: int


# ============================================================================
# v1.3 — documents & interview transcripts
# ============================================================================

# ---------- v1.3 enums ----------

class InterviewFormat(str, Enum):
    onsite = "onsite"
    video = "video"
    phone = "phone"
    other = "other"


class TranscriptSource(str, Enum):
    manual = "manual"
    uploaded = "uploaded"
    auto = "auto"


class AttachmentKind(str, Enum):
    cv = "cv"
    profile = "profile"
    job_spec = "job_spec"
    transcript_file = "transcript_file"
    reference = "reference"
    other = "other"


class AttachmentEntityType(str, Enum):
    firm = "firm"
    partner = "partner"
    org = "org"
    engagement = "engagement"
    interview = "interview"


# ---------- v1.3 record models ----------

class InterviewRecord(_Base):
    id: int
    ulid: str
    engagement_id: int
    engagement_log_id: int | None = None
    interview_date: date
    round: int | None = None
    format: InterviewFormat | None = None
    panel: str | None = None
    summary: str | None = None
    transcript: str | None = None
    transcript_source: TranscriptSource | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class AttachmentRecord(_Base):
    """Metadata only — deliberately omits the `content` BLOB so bytes can never
    flow through to_response / model_dump. Bytes are read solely via
    attachments_repo.get_content."""
    id: int
    ulid: str
    entity_type: AttachmentEntityType
    entity_id: str
    kind: AttachmentKind
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    uploaded_by: str
    created_at: datetime
    deleted_at: datetime | None = None


# ---------- v1.3 input models ----------

class LogInterviewInput(BaseModel):
    engagement_ulid: str
    interview_date: date
    round: int | None = None
    format: InterviewFormat | None = None
    panel: str | None = None
    summary: str | None = None
    transcript: str | None = None
    transcript_source: TranscriptSource | None = None


class SetTranscriptInput(BaseModel):
    interview_ulid: str
    transcript: str
    transcript_source: TranscriptSource = TranscriptSource.manual


class InterviewUpdateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    interview_date: date | None = None
    round: int | None = None
    format: InterviewFormat | None = None
    panel: str | None = None
    summary: str | None = None


class GetInterviewInput(BaseModel):
    interview_ulid: str
    include_transcript: bool = False


class ListInterviewsInput(BaseModel):
    engagement_ulid: str


class AttachFileInput(BaseModel):
    entity_type: AttachmentEntityType
    entity_ulid: str
    kind: AttachmentKind
    filename: str
    content_type: str
    content_base64: str


class GetAttachmentInput(BaseModel):
    attachment_ulid: str


class ListAttachmentsInput(BaseModel):
    entity_type: AttachmentEntityType
    entity_ulid: str
