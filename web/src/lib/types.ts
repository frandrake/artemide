// Mirror of src/models.py — kept in sync manually until we autogenerate
// from OpenAPI. Field names match the JSON shape returned by REST after
// the integer-PK strip in src/api/_serde.py.

export type FirmTier = 'primary' | 'specialist' | 'ned';
export type RelationshipState = 'cold' | 'warming' | 'warm' | 'dormant';
export type ContactChannel =
  | 'email' | 'call' | 'coffee' | 'event' | 'inmail' | 'message' | 'other';
export type InitiatedBy = 'me' | 'them';
export type NoteEntityType = 'firm' | 'partner' | 'org' | 'engagement';
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
  partner_ulid: string | null;
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
  stage_advanced: boolean;
  new_stage: OutreachStage | null;
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
  suggested_next_touch_date: string | null;
  due_source: 'planned' | 'cadence' | 'none';
  cadence_ideal_days: number | null;
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

// ============================================================================
// v1.2 — engagement & programme extension
// ============================================================================

export type ScaleBand = 'fortune_500' | 'global_equivalent' | 'pe_backed' | 'other';
export type WatchState = 'watch' | 'target' | 'active' | 'parked' | 'excluded';
export type RoleType = 'cmo' | 'cmgo' | 'cco' | 'transformation' | 'ned' | 'other';
export type EngagementSource =
  | 'inbound_partner' | 'radar' | 'referral' | 'direct' | 'flywheel' | 'other';
export type EngagementStage =
  | 'surfaced' | 'exploratory' | 'formal' | 'final' | 'offer' | 'decision' | 'closed';
export type EngagementInterest = 'pass' | 'exploratory' | 'active' | 'preferred';
export type MessageKind =
  | 'inbound_reply' | 'cadence_touch' | 'cold_outreach' | 'thank_you' | 'custom';
export type MessageChannel = 'email' | 'inmail' | 'message';
export type MessageStatus = 'proposed' | 'approved' | 'edited' | 'sent' | 'discarded';
export type MilestonePhase = 'build' | 'seed' | 'run' | 'close' | 'exit';
export type MilestoneStatus = 'pending' | 'on_track' | 'at_risk' | 'done';
export type Rag = 'green' | 'amber' | 'red';

export const STAGE_ORDER: EngagementStage[] = [
  'surfaced', 'exploratory', 'formal', 'final', 'offer', 'decision',
];

export interface Org {
  ulid: string;
  name: string;
  sector: string | null;
  scale_band: ScaleBand | null;
  hq_region: string | null;
  pertinence_note: string | null;
  watch_state: WatchState;
  source: string | null;
  external_refs: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  engagements?: Engagement[];
  notes?: Note[];
}

export interface Engagement {
  ulid: string;
  org_ulid: string | null;
  org_name: string | null;
  org_scale_band: ScaleBand | null;
  role_title: string;
  role_type: RoleType | null;
  source: EngagementSource | null;
  source_partner_ulid: string | null;
  source_partner_name: string | null;
  stage: EngagementStage;
  interest: EngagementInterest;
  comp_base_gbp: number | null;
  comp_total_gbp: number | null;
  comp_equity_note: string | null;
  fit_score: number | null;
  fit_breakdown: Record<string, unknown> | string | null;
  next_step: string | null;
  next_step_date: string | null;
  closed_reason: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  log?: EngagementLogEntry[];
  notes?: Note[];
  reciprocity_suggestion?: string | null;
}

export interface EngagementLogEntry {
  ulid: string;
  event_date: string;
  event_type: string;
  from_stage: string | null;
  to_stage: string | null;
  summary: string | null;
  created_at: string;
}

export interface Message {
  ulid: string;
  kind: MessageKind | null;
  partner_ulid: string | null;
  partner_name?: string | null;
  engagement_ulid: string | null;
  channel: MessageChannel | null;
  recipient_hint: string | null;
  subject: string | null;
  body: string;
  rationale: string | null;
  status: MessageStatus;
  source_ref: string | null;
  created_by_transport: string | null;
  approved_at: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FitProfile {
  ulid: string;
  version: number;
  active: number;
  comp_base_floor_gbp: number;
  comp_total_target_gbp: number;
  accepted_role_types: string[];
  accepted_scale_bands: string[];
  hard_exclusions: string[];
  weights: Record<string, number>;
  created_at: string;
}

export interface Milestone {
  ulid: string;
  phase: MilestonePhase | null;
  label: string;
  target_date: string;
  status: MilestoneStatus;
  metric_note: string | null;
}

export interface ProgrammePhase {
  phase: string;
  rag: Rag;
  detail: string;
}

export interface ProgrammeStatus {
  days_to_target: number;
  target_date: string;
  overall_rag: Rag;
  target_at_risk: boolean;
  phases: ProgrammePhase[];
}

export interface OutboxEvent {
  ulid: string;
  event_type: string;
  entity_type: string;
  entity_ulid: string;
  payload: string | null;
  created_at: string;
  delivered_at: string | null;
  delivery_attempts: number;
}

export interface OutboxHealth {
  undelivered: number;
  oldest_undelivered_age_seconds: number | null;
  past_attempt_cap: number;
}

// ---------- v1.3: documents & interview transcripts ----------

export type InterviewFormat = 'onsite' | 'video' | 'phone' | 'other';
export type TranscriptSource = 'manual' | 'uploaded' | 'auto';
export type AttachmentKind =
  | 'cv' | 'profile' | 'job_spec' | 'transcript_file' | 'reference' | 'other';
export type AttachmentEntityType =
  | 'firm' | 'partner' | 'org' | 'engagement' | 'interview';

export interface Interview {
  ulid: string;
  engagement_ulid?: string | null;
  interview_date: string;
  round: string | null;
  format: InterviewFormat | null;
  panel: string | null;
  summary: string | null;
  // Present only when fetched with ?include_transcript=true.
  transcript?: string | null;
  transcript_source: TranscriptSource | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

// ---------- compensation scenarios ----------

export type CompScenarioStatus = 'current' | 'offer' | 'negotiating' | 'accepted' | 'rejected';

export interface CompTotals {
  pension_value_gbp: number;
  total_cash_gbp: number;
  total_gbp: number;
}

export interface CompScenario {
  ulid: string;
  name: string;
  status: CompScenarioStatus;
  is_baseline: boolean;
  engagement_ulid: string | null;
  engagement_role_title: string | null;
  engagement_org_name: string | null;
  base_gbp: number | null;
  cash_bonus_gbp: number | null;
  equity_gbp: number | null;
  equity_note: string | null;
  pension_pct: number | null;
  healthcare_gbp: number | null;
  car_allowance_gbp: number | null;
  other_gbp: number | null;
  benefits_note: string | null;
  totals: CompTotals;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface Attachment {
  ulid: string;
  entity_type: AttachmentEntityType;
  entity_id: string;
  kind: AttachmentKind;
  filename: string;
  content_type: string;
  byte_size: number;
  sha256: string;
  uploaded_by: string;
  created_at: string;
  deleted_at: string | null;
}

export interface CompDelta {
  baseline: number;
  scenario: number;
  delta_gbp: number;
  delta_pct: number | null;
}

export interface CompComparison {
  baseline: CompScenario;
  scenarios: (CompScenario & { deltas: Record<string, CompDelta> })[];
}

// ============================================================================
// Board / NED search domain — parallel to the executive search, owner-only.
// ============================================================================

export type BoardFirmType =
  | 'big_five_board_practice' | 'boutique' | 'platform' | 'network' | 'italian_european';
export type BoardGeography = 'UK' | 'Europe' | 'Italy';
export type BoardFirmStatus =
  | 'to_approach' | 'to_register' | 'to_join' | 'queued' | 'contacted' | 'in_dialogue' | 'dormant'
  | 'drafted' | 'consider' | 'monitor';
export type BoardContactPractice = 'board' | 'executive' | 'mixed';
export type BoardRelationship = 'cold' | 'warm' | 'active';
export type BoardOppBoardType =
  | 'listed_ftse350' | 'listed_aim' | 'pe_vc' | 'private' | 'mutual' | 'charity_arts' | 'public_appointment';
export type BoardOppRole = 'ned' | 'sid' | 'committee' | 'trustee' | 'adviser';
export type BoardAppointmentCategory =
  | 'ned_unspecified' | 'independent_ned' | 'non_independent_ned'
  | 'board_chair' | 'senior_independent_director' | 'committee_chair'
  | 'committee_member' | 'trustee' | 'advisory_board' | 'editorial_board'
  | 'other_board';
export type BoardFiduciaryStatus =
  | 'statutory_fiduciary' | 'contractual_non_fiduciary' | 'requires_confirmation';
export type BoardDoInsuranceStatus = 'confirmed' | 'not_confirmed' | 'pending';
export type BoardStage =
  | 'surfaced' | 'conflict_screen' | 'chair_meeting' | 'formal_process'
  | 'final_nomco' | 'offer' | 'decision';
export type BoardConflictCleared = 'yes' | 'no' | 'pending';
export type BoardConflictResult = 'pass' | 'fail' | 'pending';
export type BoardOppInterest = 'pass' | 'exploratory' | 'active' | 'preferred';
export type BoardVerdict = 'proceed' | 'proceed_with_caution' | 'pass';
export type BoardInteractionType = 'email' | 'call' | 'meeting' | 'application' | 'event' | 'note';
export type BoardLinkedEntityType = 'board_firm' | 'board_contact' | 'board_opportunity';

export const BOARD_STAGE_ORDER: BoardStage[] = [
  'surfaced', 'conflict_screen', 'chair_meeting', 'formal_process',
  'final_nomco', 'offer', 'decision',
];

export const BOARD_EVAL_DIMENSIONS: { key: string; label: string; weight: number }[] = [
  { key: 'chair_board_quality', label: 'Chair & board quality', weight: 25 },
  { key: 'mandate_contribution_fit', label: 'Mandate / contribution fit', weight: 25 },
  { key: 'governance_health_risk', label: 'Governance health / risk', weight: 20 },
  { key: 'time_conflict_cost', label: 'Time / conflict cost', weight: 15 },
  { key: 'brand_portfolio_value', label: 'Brand / portfolio value', weight: 10 },
  { key: 'terms', label: 'Terms', weight: 5 },
];

export const BOARD_HARD_DISQUALIFIERS: { key: string; label: string }[] = [
  { key: 'unclearable_sp_conflict', label: 'Unclearable S&P conflict' },
  { key: 'dominant_chair_or_factional_board', label: 'Dominant chair / factional board' },
  { key: 'decorative_seat', label: 'Decorative seat' },
  { key: 'unmanaged_governance_risk', label: 'Serious unmanaged governance/financial/litigation risk' },
  { key: 'inadequate_do_indemnification', label: 'Inadequate D&O / indemnification' },
  { key: 'performative_visibility_demanded', label: 'Constant performative visibility demanded' },
  { key: 'weak_transformation_ambition', label: 'Weak transformation ambition' },
];

export interface BoardFirm {
  ulid: string;
  name: string;
  firm_type: BoardFirmType | null;
  geography: BoardGeography[];
  sectors_level: string | null;
  ai_on_boards_hook: string | null;
  tier: number | null;
  status: BoardFirmStatus;
  next_action: string | null;
  notes: string | null;
  source_url: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  contacts?: BoardContact[];
  interactions?: BoardInteraction[];
}

export interface BoardContact {
  ulid: string;
  name: string;
  role_title: string | null;
  firm_ulid: string | null;
  firm_name: string | null;
  practice: BoardContactPractice | null;
  email: string | null;
  linkedin: string | null;
  mutual_connections: string | null;
  relationship: BoardRelationship;
  last_contact_date: string | null;
  source_url: string | null;
  notes: string | null;
  verify_before_send: boolean;
  interactions?: BoardInteraction[];
}

export interface BoardConflictScreen {
  ulid: string;
  is_sp_competitor: boolean;
  result: BoardConflictResult;
  checked_date: string | null;
  notes: string | null;
}

export interface BoardEvaluation {
  ulid: string;
  score_chair_board_quality: number | null;
  score_mandate_contribution_fit: number | null;
  score_governance_health_risk: number | null;
  score_time_conflict_cost: number | null;
  score_brand_portfolio_value: number | null;
  score_terms: number | null;
  weighted_total: number | null;
  hard_disqualifiers: string[];
  firo_b_fit_notes: string | null;
  verdict: BoardVerdict | null;
}

export interface BoardOpportunityLogEntry {
  ulid: string;
  event_date: string;
  event_type: string;
  from_stage: string | null;
  to_stage: string | null;
  summary: string | null;
  created_at: string;
}

export interface BoardInteraction {
  ulid: string;
  interaction_date: string;
  interaction_type: BoardInteractionType;
  linked_entity_type: BoardLinkedEntityType;
  linked_entity_ulid: string;
  summary: string | null;
  next_action: string | null;
  due_date: string | null;
}

export type BoardOutcome = 'accepted' | 'declined' | 'lost';

export interface BoardTarget {
  ulid: string;
  seats_target: number;
  target_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface BoardTargetStatus {
  target_set: boolean;
  seats_target: number;
  target_date: string | null;
  days_to_target: number | null;
  notes: string | null;
  seats_won: number;
  open_opportunities: number;
  funnel: Record<BoardStage, number>;
  early: number;
  mid: number;
  late: number;
  rag: 'red' | 'amber' | 'green';
}

export interface BoardOpportunity {
  ulid: string;
  organisation: string;
  board_type: BoardOppBoardType | null;
  role: BoardOppRole | null;
  appointment_category: BoardAppointmentCategory | null;
  fiduciary_status: BoardFiduciaryStatus;
  legal_entity: string | null;
  time_commitment_days: number | null;
  term_length_months: number | null;
  annual_fee_gbp: number | null;
  committee_expectations: string | null;
  independence_requirement: string | null;
  liability_indemnity_notes: string | null;
  do_insurance_status: BoardDoInsuranceStatus;
  conflicts_notes: string | null;
  due_diligence_notes: string | null;
  next_step_due_date: string | null;
  source_firm_ulid: string | null;
  source_firm_name: string | null;
  source_text: string | null;
  chair_contact_ulid: string | null;
  chair_name: string | null;
  date_surfaced: string | null;
  stage: BoardStage;
  conflict_cleared: BoardConflictCleared;
  interest: BoardOppInterest;
  next_step: string | null;
  notes: string | null;
  eval_weighted_total: number | null;
  eval_verdict: BoardVerdict | null;
  outcome: BoardOutcome | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  warnings?: string[];
  conflict_screen?: BoardConflictScreen | null;
  evaluation?: BoardEvaluation | null;
  log?: BoardOpportunityLogEntry[];
  interactions?: BoardInteraction[];
}

export interface BoardTask {
  ulid: string;
  linked_entity_type: BoardLinkedEntityType | null;
  linked_entity_ulid: string | null;
  title: string;
  due_date: string | null;
  status: 'open' | 'done';
}

export interface BoardCompetitor {
  ulid: string;
  name: string;
  notes: string | null;
  active: number;
}

export interface BoardEvaluationCompare {
  weights: Record<string, number>;
  opportunities: {
    opportunity_ulid: string;
    organisation: string;
    stage: BoardStage;
    interest: BoardOppInterest;
    weighted_total: number | null;
    verdict: BoardVerdict | null;
    scores: Record<string, number> | null;
    hard_disqualifiers: string[];
  }[];
}
