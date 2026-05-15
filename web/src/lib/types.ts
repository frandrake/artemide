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
