// Mirror of src/models.py — kept in sync manually until we autogenerate
// from OpenAPI. Field names match the JSON shape returned by REST after
// the integer-PK strip in src/api/_serde.py.

export type FirmTier = 'primary' | 'specialist' | 'ned';
export type RelationshipState = 'cold' | 'warming' | 'warm' | 'dormant';
export type ContactChannel =
  | 'email' | 'call' | 'coffee' | 'event' | 'inmail' | 'message' | 'other';
export type InitiatedBy = 'me' | 'them';
export type NoteEntityType = 'firm' | 'partner';
export type CalendarStatus = 'not_set' | 'planned' | 'in_progress' | 'complete';

export interface Firm {
  ulid: string;
  name: string;
  tier: FirmTier;
  region: string | null;
  relationship_state: RelationshipState;
  primary_focus: string | null;
  notes_summary: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  // Headhunter intelligence fields (migration 010)
  market_tier?: string | null;
  strategic_fit?: string | null;
  ned_practice_strength?: string | null;
  hq_address?: string | null;
  sectors?: string | null;
  cmo_practice_depth?: string | null;
  comp_transparency?: string | null;
  candidate_reputation?: string | null;
  b2b_fs_reputation?: string | null;
}

export interface Partner {
  ulid: string;
  name: string;
  title: string | null;
  practice: string | null;
  seniority: string | null;
  location: string | null;
  introduced_via: string | null;
  email: string | null;
  linkedin_url: string | null;
  relationship_state: RelationshipState;
  last_contact_date: string | null;
  next_touch_date: string | null;
  next_touch_topic: string | null;
  notes_summary: string | null;
  follow_ups_outstanding: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  // Populated by GET /api/v1/partners/{ulid} only.
  firm_ulid?: string;
  firm_name?: string;
  // Headhunter intelligence fields (migration 010)
  practice_focus?: string | null;
  strategic_relevance?: string | null;
  warm_intro_angle?: string | null;
  thought_leadership?: string | null;
  prior_career?: string | null;
  ned_gateway?: number;
  // Outreach pipeline stage (migration 011)
  outreach_stage?: OutreachStage;
}

// ---------- Phase 11: outreach workspace ----------

export type OutreachChannel = 'email' | 'linkedin' | 'message' | 'other';
export type DraftStatus = 'draft' | 'ready' | 'sent' | 'archived';
export type OutreachStage =
  | 'researched' | 'drafted' | 'sent' | 'replied'
  | 'met' | 'ongoing' | 'paused' | 'dropped';
export type EngagementStatus = 'not_set' | 'planned' | 'in_progress' | 'complete';

export interface EngagementCalendarRecord {
  ulid: string;
  firm_id?: number | null;
  partner_id?: number | null;
  due_date: string;
  title: string;
  description: string | null;
  status: EngagementStatus;
  track: string | null;
  created_at: string;
}

export interface TemplateRecord {
  ulid: string;
  name: string;
  category: string | null;
  channel: OutreachChannel;
  subject_template: string | null;
  body_template: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface OutreachDraftRecord {
  ulid: string;
  partner_id: number;
  template_id: number | null;
  channel: OutreachChannel;
  subject: string | null;
  body: string;
  status: DraftStatus;
  version: number;
  sent_message_id: number | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface OutreachMessageRecord {
  ulid: string;
  draft_id: number;
  partner_id: number;
  contact_log_id: number;
  sent_at: string;
  sent_via: OutreachChannel;
  recipient_handle: string | null;
  subject_snapshot: string | null;
  body_snapshot: string;
  version_sent: number;
}

export interface OutreachDraftVersionRecord {
  ulid: string;
  draft_id: number;
  version: number;
  subject: string | null;
  body: string;
  author_actor: string;
  created_at: string;
}

export interface PipelineSnapshot {
  stages: Record<OutreachStage, PipelineCard[]>;
  counts: Record<OutreachStage, number>;
}

export interface PipelineCard {
  partner_ulid: string;
  partner_name: string;
  firm_ulid: string;
  firm_name: string;
  firm_tier: FirmTier;
  strategic_relevance: string | null;
  ned_gateway: boolean;
  last_contact_date: string | null;
  next_touch_date: string | null;
  open_draft_ulid: string | null;
  sent_count: number;
  outreach_stage: OutreachStage;
}

export interface OutreachVolumePoint {
  bucket: string;
  count: number;
}

export interface ResponseRate {
  since: string;
  until: string;
  sent: number;
  incoming: number;
  rate: number;
}

export interface ReciprocityPartner {
  partner_ulid: string;
  partner_name: string;
  firm_name: string;
  given: number;
  received: number;
  balance: number;
}

export interface PlanExecution {
  since: string;
  until: string;
  complete: number;
  total: number;
  percent: number;
  by_status: Record<EngagementStatus, number>;
}

export interface ContactLog {
  ulid: string;
  contact_date: string;
  channel: ContactChannel;
  initiated_by: InitiatedBy;
  summary: string | null;
  value_given: string | null;
  value_received: string | null;
  follow_up: string | null;
  created_at: string;
}

export interface ContactLogResponse {
  contact: ContactLog;
  partner_ulid: string;
  firm_ulid: string;
  state_advanced: boolean;
  new_state: RelationshipState | null;
}

export interface Note {
  ulid: string;
  entity_type: NoteEntityType;
  entity_id: string;
  body: string;
  created_at: string;
}

export interface ValueCalendar {
  ulid: string;
  year: number;
  quarter: number;
  topic: string | null;
  status: CalendarStatus;
  created_at: string;
  updated_at: string;
}

export interface DueTouch {
  partner_ulid: string;
  partner_name: string;
  firm_ulid: string;
  firm_name: string;
  tier: FirmTier;
  last_contact_date: string | null;
  next_touch_date: string | null;
  next_touch_topic: string | null;
  days_since_last_contact: number | null;
  days_until_next_touch: number | null;
  status: 'overdue' | 'due_soon' | 'no_planned_touch';
}

export interface QuarterPlan {
  year: number;
  quarter: number;
  topic: string | null;
  topic_status: CalendarStatus | null;
  slots: {
    week_starting: string;
    firm_ulid: string;
    firm_name: string;
    partner_ulid: string | null;
    partner_name: string | null;
    rationale: string;
  }[];
  gaps: string[];
}

export interface AuditReport {
  generated_at: string;
  primary_tier_coverage: CoverageEntry[];
  specialist_tier_coverage: CoverageEntry[];
  dormant_relationships: DormantEntry[];
  open_follow_ups: FollowUpEntry[];
  reciprocity_imbalances: ReciprocityEntry[];
  summary_actions: string[];
}

export interface CoverageEntry {
  firm_ulid: string;
  firm_name: string;
  has_active_partner: boolean;
  days_since_last_contact: number | null;
  relationship_state: RelationshipState;
  flagged: boolean;
  note: string | null;
}

export interface DormantEntry {
  partner_ulid: string;
  partner_name: string;
  firm_name: string;
  tier: FirmTier;
  days_since_last_contact: number;
}

export interface FollowUpEntry {
  partner_ulid: string;
  partner_name: string;
  firm_name: string;
  items: string[];
}

export interface ReciprocityEntry {
  partner_ulid: string;
  partner_name: string;
  firm_name: string;
  given: number;
  received: number;
}

export interface AuditLogRecord {
  ulid: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  transport: string;
  payload: string | null;
  timestamp: string;
}

export interface SearchHit {
  entity_type: 'firm' | 'partner' | 'note' | 'contact';
  entity_ulid: string;
  primary_text: string;
  secondary_text: string;
  rank: number;
  entity: Record<string, unknown> | null;
}

export interface BackupEntry {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface SystemInfo {
  schema_version: string | null;
  schema_applied_at: string | null;
  build_hash: string;
  token_source: 'database' | 'environment';
  counts: { firms: number; partners: number; contacts: number; notes: number; audit_entries: number };
  dependencies: Record<string, string>;
}
