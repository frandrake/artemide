# Artemide — Technical Specification (v1.2)

**Engagement & Programme Extension**

An extension to the v1.1 relationship CRM. v1.1 manages the relationship asset — the firms and partners that matter over a long horizon. v1.2 adds the active programme layer on top: a pipeline of organisations and engagements, a fit-scoring engine, a human-approved message queue, an events outbox, programme milestones, and the n8n workflow layer that ties Claude, the bot mailbox, and external research to Artemide. Nothing in v1.1 is rewritten. Every v1.1 convention is preserved.

---

## How to read this document

This spec assumes the v1.1 specification as its base. It only describes additions and the few in-place alterations to existing tables. Where v1.1 already defines a pattern (ULID dual-identifier, soft delete, append-only audit, service/repository/transport layering, idempotency keys, Bearer auth, Cloudflare Tunnel, Milanese Futurist tokens), v1.2 follows it without restating it.

**Carried-over non-negotiables (unchanged):**

- No language in code, logs, or UI signalling a personal career search. See *Naming & discretion* below — it governs every name in this document.
- No inbound ports on the VPS; all ingress via Cloudflare Tunnel.
- Append-only audit log; soft deletes never hard-delete.
- Transports stay thin; all business logic lives in the service layer.
- No in-application email sending or parsing — n8n handles all mail out-of-band.
- No telemetry; zero outbound traffic except backups and the tunnel.

---

## Naming & discretion

v1.1 forbids any name that signals a personal career search. v1.2 holds the same line. The programme layer is modelled and named as a **business-development engagement pipeline** — plausible, coherent on its own terms, and indistinguishable from a senior operator tracking inbound mandates. The mapping to the real-world objective lives only in the confidential plan document, never in this repo.

Neutral glossary used throughout this spec:

| Neutral name (in code, DB, UI) | Definition |
|---|---|
| `organisations` (orgs) | Organisations of interest in the programme |
| `engagements` | Specific mandates or roles in motion |
| `engagement_log` | Stage history and events on an engagement |
| `engagement_profile` | The fit criteria the programme scores against |
| `messages` | Outbound draft queue awaiting approval |
| `programme_milestones` | Time-boxed programme milestones |
| `programme_status` | Phase RAG and slippage check |
| `programme_target_date` | The date the programme works back from |

The rest of this document uses only the neutral names.

---

## What v1.2 adds — at a glance

1. **Organisations & engagements pipeline** — the missing system of record for *what* is in motion, linked to the firms/partners that surface it.
2. **Fit-scoring engine** — scores every engagement 0–100 against an editable `engagement_profile`, with hard filters and weighted dimensions.
3. **Message queue with human-only approval** — Claude and n8n propose; only the owner approves; approval is enforced server-side and can never be performed by the bot actor.
4. **Events outbox** — the v1.1-reserved outbox, now built, so n8n can react to state changes without polling business tables.
5. **Programme milestones & status** — milestones working back from `programme_target_date`, plus a RAG slippage check.
6. **n8n workflow layer** — seven workflows mapped onto Artemide's REST API, the bot mailbox, external research, and Claude. Specified as an appendix; n8n holds the orchestration, Artemide holds the state.
7. **Bot actor & token roles** — the v1.1-reserved multi-actor model, now built, with an `owner`/`bot` role split and enforced scopes.

---

## Data Model — additions

All new primary entities follow the v1.1 identifier strategy (`id` INTEGER PK AUTOINCREMENT + `ulid` TEXT UNIQUE), use `created_at`/`updated_at` with trigger-updated `updated_at`, and are covered by the audit log. Soft delete (`deleted_at`) applies to `organisations` and `engagements` only; logs and the outbox are append-only.

### Entity: `organisations`

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | Internal |
| `ulid` | TEXT | NOT NULL, UNIQUE | External ID |
| `name` | TEXT | NOT NULL, UNIQUE (where deleted_at IS NULL) | |
| `sector` | TEXT | nullable | |
| `scale_band` | TEXT | CHECK IN ('fortune_500','global_equivalent','pe_backed','other') | |
| `hq_region` | TEXT | nullable | |
| `pertinence_note` | TEXT | nullable | Why a move here is coherent with the narrative |
| `watch_state` | TEXT | CHECK IN ('watch','target','active','parked','excluded'), default 'watch' | |
| `source` | TEXT | nullable | How surfaced |
| `external_refs` | TEXT | nullable | JSON: `{capiq_id, website, linkedin}` |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Trigger-updated |
| `deleted_at` | TIMESTAMP | nullable | Soft delete |

### Entity: `engagements`

The pipeline entity. One row per role-in-motion at an organisation.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `org_id` | INTEGER | NOT NULL, FK → organisations(id) | |
| `role_title` | TEXT | NOT NULL | |
| `role_type` | TEXT | CHECK IN ('cmo','cmgo','cco','transformation','ned','other') | |
| `source` | TEXT | CHECK IN ('inbound_partner','radar','referral','direct','flywheel','other') | |
| `source_partner_id` | INTEGER | nullable, FK → partners(id) | Which partner surfaced it — links pipeline to the relationship asset |
| `stage` | TEXT | CHECK IN ('surfaced','exploratory','formal','final','offer','decision','closed'), default 'surfaced' | |
| `interest` | TEXT | CHECK IN ('pass','exploratory','active','preferred'), default 'exploratory' | |
| `comp_base_gbp` | INTEGER | nullable | |
| `comp_total_gbp` | INTEGER | nullable | |
| `comp_equity_note` | TEXT | nullable | |
| `fit_score` | INTEGER | nullable | 0–100, computed by FitService |
| `fit_breakdown` | TEXT | nullable | JSON per-dimension scores + hard-filter result |
| `next_step` | TEXT | nullable | |
| `next_step_date` | DATE | nullable | |
| `closed_reason` | TEXT | CHECK IN ('withdrew','rejected','declined_offer','accepted','lapsed') nullable | Set only when stage='closed' |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Trigger-updated |
| `deleted_at` | TIMESTAMP | nullable | Soft delete |

INDEX on `org_id`, `stage`, `interest`, `next_step_date`, `source_partner_id` (all WHERE deleted_at IS NULL).

### Entity: `engagement_log`

Append-only. Stage moves and key events (interview, reference, offer detail).

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `engagement_id` | INTEGER | NOT NULL, FK → engagements(id) | |
| `event_date` | DATE | NOT NULL | |
| `event_type` | TEXT | CHECK IN ('stage_change','interview','reference','offer','note','withdrawal') | |
| `from_stage` | TEXT | nullable | Set when event_type='stage_change' |
| `to_stage` | TEXT | nullable | Set when event_type='stage_change' |
| `summary` | TEXT | nullable | |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |

INDEX on `engagement_id`, `event_date`.

### Entity: `engagement_profile`

The fit criteria. Versioned; exactly one row is `active`.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `version` | INTEGER | NOT NULL | |
| `active` | INTEGER | NOT NULL, default 0 | Boolean; partial unique index enforces one active |
| `comp_base_floor_gbp` | INTEGER | NOT NULL | |
| `comp_total_target_gbp` | INTEGER | NOT NULL | |
| `accepted_role_types` | TEXT | NOT NULL | JSON array |
| `accepted_scale_bands` | TEXT | NOT NULL | JSON array |
| `hard_exclusions` | TEXT | NOT NULL | JSON array of tags (e.g. `["custodial_brand_only","high_politics"]`) |
| `weights` | TEXT | NOT NULL | JSON map: dimension → integer weight (sum 100) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |

Partial unique index: `CREATE UNIQUE INDEX idx_profile_active ON engagement_profile(active) WHERE active = 1;`

Seed values (from the plan): base floor £250,000; total target £500,000; accepted role types `['cmo','cmgo','cco','transformation']`; accepted scale bands `['fortune_500','global_equivalent']`; hard exclusions `['custodial_brand_only','high_politics','micromanaging_board','performative_visibility','weak_transformation']`; default weights below.

### Entity: `messages`

The outbound draft queue. The human gate. Append-mostly: edits update `body`/`status` in place but the audit log retains every prior state.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `kind` | TEXT | CHECK IN ('inbound_reply','cadence_touch','cold_outreach','thank_you','custom') | |
| `partner_id` | INTEGER | nullable, FK → partners(id) | |
| `engagement_id` | INTEGER | nullable, FK → engagements(id) | |
| `channel` | TEXT | CHECK IN ('email','inmail','message') | |
| `recipient_hint` | TEXT | nullable | Display name only; no address stored here |
| `subject` | TEXT | nullable | |
| `body` | TEXT | NOT NULL | The proposed message |
| `rationale` | TEXT | nullable | Why drafted (e.g. "cadence overdue 132d") |
| `status` | TEXT | CHECK IN ('proposed','approved','edited','sent','discarded'), default 'proposed' | |
| `source_ref` | TEXT | nullable | Opaque external ref (e.g. inbound mail id) for idempotency |
| `created_by_transport` | TEXT | CHECK IN ('mcp','rest','system') | n8n writes as 'rest' |
| `approved_at` | TIMESTAMP | nullable | |
| `sent_at` | TIMESTAMP | nullable | |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Trigger-updated |

INDEX on `status`, `partner_id`, `engagement_id`. UNIQUE on `source_ref` WHERE `source_ref IS NOT NULL` (inbound idempotency).

### Entity: `events_outbox`

Append-only. The event source n8n consumes. Builds the v1.1-reserved outbox pattern.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | Used as the idempotency key by consumers |
| `event_type` | TEXT | NOT NULL | e.g. 'engagement.surfaced','engagement.stage_changed','message.approved','touch.overdue','programme.rollup_due' |
| `entity_type` | TEXT | NOT NULL | |
| `entity_ulid` | TEXT | NOT NULL | |
| `payload` | TEXT | nullable | JSON snapshot the consumer needs |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `delivered_at` | TIMESTAMP | nullable | Set on consumer ack |
| `delivery_attempts` | INTEGER | NOT NULL, default 0 | |

INDEX on `delivered_at`, `event_type`, `created_at`.

### Entity: `programme_milestones`

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `phase` | TEXT | CHECK IN ('build','seed','run','close','exit') | |
| `label` | TEXT | NOT NULL | |
| `target_date` | DATE | NOT NULL | |
| `status` | TEXT | CHECK IN ('pending','on_track','at_risk','done'), default 'pending' | |
| `metric_note` | TEXT | nullable | The measurable condition (e.g. "≥5 warm partners") |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Trigger-updated |

### Entity: `api_tokens`

Builds the v1.1-reserved multi-actor model. One row per issued token; the API token value is never stored — only its hash.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `ulid` | TEXT | NOT NULL, UNIQUE | |
| `token_hash` | TEXT | NOT NULL, UNIQUE | SHA-256 of the bearer token |
| `actor` | TEXT | NOT NULL | e.g. 'FF', 'n8n_bot' |
| `role` | TEXT | NOT NULL, CHECK IN ('owner','bot') | |
| `active` | INTEGER | NOT NULL, default 1 | |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | |
| `rotated_at` | TIMESTAMP | nullable | |

### In-place alterations to v1.1 tables

SQLite `CHECK` changes require a table rebuild (create new, copy, drop, rename) — handle inside the migration with `PRAGMA foreign_keys=OFF` and a transaction. (Note in this repo: the migration runner already wraps each migration in a single transaction and `PRAGMA foreign_keys` cannot be toggled inside one — `notes` and `contact_log` are leaf tables referenced by no other FK, so the rebuild is performed directly within that transaction.)

- **`notes.entity_type`** — extend CHECK to `IN ('firm','partner','org','engagement')`. Lets dossiers and prep packs attach to organisations and engagements.
- **`contact_log.engagement_id`** — add nullable `INTEGER FK → engagements(id)`. Links a logged contact to the engagement it concerned, so relationship activity and pipeline activity reconcile.
- **`audit_log.entity_type`** — no schema change needed. New values used: 'org','engagement','message','profile','milestone'. Transport stays the v1.1 set; n8n authenticates as actor `n8n_bot`, transport `'rest'`.
- **`search_index` (FTS5)** — add `org` and `engagement` rows (org name + pertinence_note; engagement role_title + org name + dossier note bodies). Sync triggers extended in the search-index migration.

### Triggers

Add `updated_at` triggers for `organisations`, `engagements`, `messages`, `programme_milestones`, mirroring the v1.1 trigger pattern. Audit rows continue to be written in the service layer, not by triggers.

---

## Service Layer — additions

New service modules, same contract as v1.1: every method takes explicit `actor` and `transport`; every mutation calls `AuditService.record(...)`; transports stay thin.

**`OrgsService`** — list (filter: watch_state, scale_band, sector), get_by_ulid, get_by_name, upsert, set_watch_state, soft_delete, restore.

**`EngagementsService`** — list (filter: stage, interest, org, source_partner), get_by_ulid, upsert, advance_stage, set_interest, set_comp, close, soft_delete, restore. `advance_stage` and `close` write an `engagement_log` row and emit an outbox event.

**`FitService`** — score(engagement) → `{score, breakdown, hard_fail}`; rescore_all; get_active_profile; set_active_profile (creates a new version, deactivates the prior). Pure function over the active `engagement_profile`; no side effects beyond writing `fit_score`/`fit_breakdown` back onto the engagement.

**`MessagesService`** — propose (status='proposed'), list (filter: status, partner, engagement), get_by_ulid, edit (owner only), approve (owner only — emits `message.approved`), mark_sent (sets sent_at; n8n calls this after sending), discard.

**`OutboxService`** — emit(event_type, entity, payload) (called by other services after relevant mutations), list_undelivered(limit), mark_delivered(ulid), and a sweep that increments `delivery_attempts` and flags events exceeding the attempt cap.

**`ProgrammeService`** — list_milestones, upsert_milestone, set_milestone_status, and `status()` — the RAG slippage check (Rule 16). Also `days_to_target()` from `programme_target_date`.

**Extensions to existing services**

- **`ContactsService.log`** — accepts optional `engagement_id`. When the contact concerns an engagement surfaced by a partner, and `value_received` is populated, it nudges the reciprocity counters used by the v1.1 audit (Rule 15).
- **`AuditService`** — recognises the new entity types in reports.
- **`SearchService`** — indexes and searches orgs and engagements alongside the v1.1 entities.

---

## Business Logic — additions

One source of truth. These rules live only in the service layer.

**Rule 13 — Fit scoring.** `FitService.score(engagement)` against the active `engagement_profile`:

1. **Hard filters (gate).** Fail if any: `role_type` not in `accepted_role_types`; `scale_band` of the org not in `accepted_scale_bands`; any org or engagement tag present in `hard_exclusions`; `comp_base_gbp` known and below `comp_base_floor_gbp`. A hard fail sets `hard_fail=true` and caps `fit_score` at 39 (so it sorts below soft-scored engagements) — it does not delete or hide the row.
2. **Soft score (weighted).** Each dimension scored 0–100, multiplied by its weight, summed, rounded. Default weights (sum 100): `role_type` 20, `scale` 15, `comp` 20, `pertinence` 15, `geography` 10, `autonomy_signal` 10, `politics_signal` 10. The `comp` dimension scores on distance to `comp_total_target_gbp` (100 at or above target, scaling down below). `politics_signal` is inverse — high politics scores low. Unknown dimensions score 50 (neutral) so an unscored engagement is not unduly punished.
3. Result `{score, breakdown, hard_fail}` is written to `fit_score`/`fit_breakdown`. Weights are read from the profile, so retuning needs no code change.

**Rule 14 — Stage progression.** `advance_stage` permits only forward transitions `surfaced → exploratory → formal → final → offer → decision`, plus `any → closed`. Any other transition returns 422. On success it writes an `engagement_log` stage_change row and emits `engagement.stage_changed`. Reaching `formal` additionally emits the event the Interview-Prep workflow consumes. Reaching `offer` flips any relevant `programme_milestone` toward `done` via ProgrammeService.

**Rule 15 — Pipeline ↔ relationship reciprocity.** When an engagement with `source_partner_id` set advances a stage, ProgrammeService suggests (does not auto-write) a `value_received` note against that partner, surfaced in the partner page. This keeps the v1.1 reciprocity ledger honest: progress a partner brings you is value received.

**Rule 16 — Programme status (RAG).** `ProgrammeService.status()` compares live metrics to milestone targets and returns per-phase `green | amber | red` plus an overall `target_at_risk` boolean. Default thresholds, working back from `programme_target_date`:

- Seed phase green if ≥5 partners at `relationship_state` in ('warm','warming') by the seed milestone date; amber if 3–4; red if <3.
- Run phase green if ≥2 engagements at stage ('formal','final') by the run milestone date; amber if 1; red if 0.
- Close phase green if ≥1 engagement at stage ('offer','decision') by twelve days before `programme_target_date`; red otherwise.
- `target_at_risk = true` if Close is red, or Run has been red for two consecutive weekly evaluations.

**Rule 17 — Message lifecycle and the human gate (cardinal rule).** Messages are created only as `proposed`. The transition to `approved` is permitted **only** for tokens with role `owner`; a `bot`-role token calling approve returns 403. There is no path, for any actor, that sends a message directly — approval emits `message.approved` to the outbox, and an external consumer (n8n) performs the send and then calls `mark_sent`. Artemide never sends. This is the rule that makes the whole system safe to automate.

**Rule 18 — Token roles and scopes.** Auth middleware resolves the bearer token to an `api_tokens` row, setting `request.state.actor` and `request.state.role`. Role `owner` may call everything. Role `bot` may: read all GET endpoints; create orgs, engagements, contacts, notes, and proposed messages; advance engagement stages; ack outbox events. Role `bot` may **not**: approve messages, soft-delete or restore anything, set the active engagement profile, or rotate tokens. Forbidden calls return 403 and are audited.

**Rule 19 — Outbox delivery.** At-least-once. Consumers dedupe on `events_outbox.ulid`. The sweep retries undelivered events; after the attempt cap (default 10) an event is left undelivered and flagged in Settings → outbox health. Emitting is best-effort and never blocks the originating mutation.

**Rule 20 — Inbound idempotency.** A proposed message carrying a `source_ref` (e.g. an inbound mail id) is unique on that ref; a second propose with the same ref returns the original. This stops the Inbound-Triage workflow double-drafting on mailbox re-reads.

---

## REST API — additions

Base path `/api/v1/`. Bearer auth on all except `/health`. ULIDs in URLs. Idempotency-Key header on all writes (per v1.1).

| Method | Path | Purpose | Min role |
|---|---|---|---|
| GET | `/orgs` | List orgs; `?watch_state=&scale_band=&sector=` | bot |
| POST | `/orgs` | Upsert org (idempotency-key) | bot |
| GET | `/orgs/{ulid}` | Org + its engagements + notes | bot |
| PATCH | `/orgs/{ulid}` | Update fields / watch_state | bot |
| DELETE | `/orgs/{ulid}` | Soft delete | owner |
| POST | `/orgs/{ulid}/restore` | Restore | owner |
| GET | `/engagements` | List; `?stage=&interest=&org_ulid=&partner_ulid=&sort=fit` | bot |
| POST | `/engagements` | Upsert engagement (idempotency-key) | bot |
| GET | `/engagements/{ulid}` | Full payload: log, comp, fit breakdown, linked partner, notes | bot |
| PATCH | `/engagements/{ulid}` | Update fields | bot |
| POST | `/engagements/{ulid}/advance` | Advance stage `{to_stage, summary}` | bot |
| POST | `/engagements/{ulid}/close` | Close `{closed_reason, summary}` | bot |
| DELETE | `/engagements/{ulid}` | Soft delete | owner |
| POST | `/engagements/{ulid}/restore` | Restore | owner |
| POST | `/engagements/{ulid}/rescore` | Recompute fit | bot |
| GET | `/fit/profile` | Active engagement profile | bot |
| PUT | `/fit/profile` | Set active profile (new version) | owner |
| POST | `/fit/rescore-all` | Rescore every open engagement | owner |
| GET | `/messages` | List; `?status=proposed&partner_ulid=&engagement_ulid=` | bot |
| POST | `/messages` | Propose a message (idempotency-key; `source_ref` for inbound) | bot |
| GET | `/messages/{ulid}` | Single message | bot |
| PATCH | `/messages/{ulid}` | Edit body/subject (sets status='edited') | owner |
| POST | `/messages/{ulid}/approve` | Approve — emits `message.approved` | **owner only** |
| POST | `/messages/{ulid}/sent` | Mark sent (n8n calls after sending) | bot |
| POST | `/messages/{ulid}/discard` | Discard | owner |
| GET | `/events` | List undelivered outbox events; `?limit=50` | bot |
| POST | `/events/{ulid}/ack` | Mark delivered | bot |
| GET | `/programme/status` | RAG + days-to-target | bot |
| GET | `/programme/milestones` | List milestones | bot |
| POST | `/programme/milestones` | Upsert milestone | owner |
| PATCH | `/programme/milestones/{ulid}` | Update status/target | owner |

Error shapes, pagination, and status codes per v1.1. A 403 from a role check uses `{"error":"forbidden_role","message":"..."}`.

---

## MCP Tools — additions

Mounted at `/mcp`, thin wrappers over services, same shape discipline as the v1.1 eight. Eight new tools so Claude can run the programme conversationally. The bot-role restriction (Rule 18) applies to the token Claude uses if that token is `bot`; if Claude uses the owner token, `approve_message` is available.

9. `upsert_org` → `OrgsService.upsert()`
10. `upsert_engagement` → `EngagementsService.upsert()`
11. `advance_engagement` → `EngagementsService.advance_stage()`
12. `list_pipeline` → `EngagementsService.list(sort='fit')` — returns engagements grouped by stage with fit scores
13. `queue_message` → `MessagesService.propose()` — Claude writes the drafted body in; it lands as `proposed`
14. `list_messages` → `MessagesService.list(status='proposed')` — the approval queue
15. `approve_message` → `MessagesService.approve()` — owner token only
16. `programme_status` → `ProgrammeService.status()` — RAG + days to target

Returns include `ulid` on every entity, consistent with the REST API.

---

## UI / UX — additions

Milanese Futurist tokens unchanged. New routes, new feature components. Labels stay neutral.

> **Repo note:** v1.1 already owns `/pipeline` (Outreach pipeline) and `/engagement` (Engagement calendar). To avoid collision the v1.2 engagements board ships at **`/engagements`** (index), not `/pipeline`.

### New page routes

| Route | Purpose | Auth |
|---|---|---|
| `/engagements` | Engagements board grouped by stage; fit-score column; filters | Required |
| `/orgs` | Organisations grouped by watch_state | Required |
| `/orgs/[ulid]` | Org detail + linked engagements + dossier notes | Required |
| `/engagements/[ulid]` | Engagement detail | Required |
| `/messages` | The approval inbox — proposed messages | Required |
| `/programme` | Phase RAG, milestones, days-to-target | Required |

### Dashboard additions

Above the v1.1 cards, a slim **programme banner**: overall RAG dot, days to `programme_target_date`, and a one-line slippage note. Two new cards: **Pipeline by stage** (horizontal stage counts, clickable into the board pre-filtered; preferred-interest engagements carry a Slate Blue marker) and **Awaiting approval** (count of `proposed` messages with a CTA to `/messages`; Vermillion left-border when non-zero — the one place a number should pull the eye).

### `/messages` — the approval inbox (most important new screen)

The human gate. List of `proposed` messages, newest first. Each row expands to show: kind, channel, recipient hint, linked partner/engagement, the `rationale`, and the full editable `body`. Three actions: **Approve** (Vermillion primary — emits the event, n8n sends), **Edit** (inline; saving sets `edited`, still requires a separate Approve), **Discard** (Ghost). No bulk-approve in v1.2. Empty state: "Nothing awaiting approval."

### `/engagements` — engagements board

Columns for each stage `surfaced → exploratory → formal → final → offer → decision`; closed engagements behind a toggle. Each card: org name (Crimson Pro), role title, fit score (badge — Slate Blue ≥70, Light Gray 40–69, Dormant Gray with a quiet flag icon when `hard_fail`), interest pill, next step + date. Cards link to `/engagements/[ulid]`. Filter bar: interest, scale band, source partner. Default sort within a column: fit score descending.

### `/engagements/[ulid]` — engagement detail

Header: org name + role title (Crimson Pro 36px), stage pill, interest pill, fit score badge, "Advance stage" button. Left panel: comp (base/total/equity note, inline-editable), fit breakdown (per-dimension bars; hard-filter result called out plainly if failed), linked partner. Right panel: next step + date, and the engagement log as a vertical timeline. Full-width below: dossier and prep-pack notes, newest first, with "Add note".

### `/orgs` and `/orgs/[ulid]`

`/orgs`: cards grouped by watch_state (target, active, watch, parked, excluded). Each: name, sector, scale band badge, count of open engagements. `/orgs/[ulid]`: header with watch-state pill and inline pertinence note; linked engagements grid; dossier notes section.

### `/programme`

Five phase cards (build, seed, run, close, exit) along a horizontal track, current phase expanded. Each milestone: label, target date, RAG status, metric note. A prominent days-to-target figure. The slippage check rendered as a short plain-English read-out, not a chart.

### Settings additions

- **Engagement profile** — view/edit comp floor, comp target, accepted role types, accepted scale bands, hard exclusions, and dimension weights. Saving creates a new profile version and offers "rescore all open engagements".
- **Automation** — issue/rotate the bot-role token (display once); outbox health (undelivered count, oldest undelivered age, any events past the attempt cap, with a "retry now" action).

### States

Every new page handles Skeleton / EmptyState / ErrorBoundary exactly as v1.1.

---

## n8n Workflow Layer (appendix)

n8n holds orchestration; Artemide holds state. Every workflow authenticates with the **bot-role** token (read, create, propose, advance, ack — never approve, never delete). Mail is sent only from the bot mailbox, and only after an owner approval has emitted `message.approved`. Claude does classification and drafting; Artemide does scoring and persistence. External company data comes from the connected company-data MCP.

| # | Workflow | Trigger | Artemide calls | Claude role | Human gate |
|---|---|---|---|---|---|
| 1 | **Radar** | Schedule, daily 06:00 | `POST /orgs` (upsert), `POST /engagements` (surfaced), `POST /engagements/{ulid}/rescore` | Classify relevance; summarise the morning digest | Owner reads digest, flags what to action |
| 2 | **Cadence** | Schedule, weekly + on due dates | `GET /planning/due-touches`, `POST /messages` (proposed, kind='cadence_touch') | Draft each warm check-in in voice | Owner approves in `/messages` |
| 3 | **Inbound triage** | Bot-mailbox watch | `POST /orgs`, `POST /engagements`, `POST /messages` (proposed, kind='inbound_reply', `source_ref`=mail id) | Classify relevant/borderline/off; draft a calibrated reply | Owner approves; high-priority pinged |
| 4 | **Dossier** | Outbox `engagement.surfaced` (or manual tag) | company-data MCP reads; `POST /notes` (entity_type='org' or 'engagement') | Assemble the structured brief | None — read-only intelligence |
| 5 | **Prep pack** | Outbox `engagement.stage_changed` → `formal` | `GET /engagements/{ulid}`, `POST /notes` (entity_type='engagement') | Build SRA story bank, themes, questions | Owner reviews before interview |
| 6 | **Flywheel** | Schedule, weekly | `POST /orgs`, `POST /engagements` (source='flywheel') | Match engagement signals to the org list | Owner decides whether to act |
| 7 | **Rollup** | Schedule, Friday 16:00 | `GET /programme/status`, `GET /engagements`, `GET /messages?status=proposed` | Compose the Friday read-out | Owner reviews; replan if red |

**The send loop (workflows 2, 3):** Artemide emits `message.approved` only after the owner approves in the UI. A dedicated n8n "Sender" workflow consumes that event, sends from the bot mailbox, then calls `POST /messages/{ulid}/sent`. No other path sends mail.

Each workflow is idempotent: it dedupes on Artemide ULIDs and outbox event ULIDs, and uses Idempotency-Key on every write. n8n workflow JSON exports live in `n8n/` with a README documenting required credentials — credentials themselves never committed.

---

## Migrations — additions

Append to the v1.1 migration chain. **Repo note:** v1.1 already occupies `001`–`011`, so the ten v1.2 migrations are numbered **`012`–`021`** (the spec's original "006–015" numbering is superseded):

```
012_organisations.sql          # orgs table + triggers + indexes
013_engagements.sql            # engagements + engagement_log + triggers + indexes
014_engagement_profile.sql     # profile table + partial unique active index + seed row
015_messages.sql               # message queue + triggers + indexes + source_ref unique
016_events_outbox.sql          # outbox + indexes
017_programme_milestones.sql   # milestones + triggers + seed rows from the plan
018_api_tokens.sql             # token table + role; backfill existing token as actor 'FF' role 'owner'
019_alter_notes_entity_types.sql   # rebuild notes with extended CHECK ('firm','partner','org','engagement')
020_alter_contact_log_engagement.sql # add contact_log.engagement_id FK
021_search_index_v2.sql        # extend FTS5 + sync triggers for orgs/engagements/dossier notes
```

Each migration is forward-only and idempotent on re-run (guard with existence checks). The two `ALTER`-by-rebuild migrations wrap their work in the runner's transaction; `notes`/`contact_log` are leaf tables, so the rebuild is FK-safe without toggling `PRAGMA foreign_keys`.

---

## Configuration & Environment — additions

Append to `.env.example`:

```
# v1.2
ARTEMIDE_N8N_TOKEN=replace-with-openssl-rand-hex-32   # bot-role token, issued via Settings
ARTEMIDE_PROGRAMME_TARGET_DATE=2027-04-05             # the date the programme works back from
ARTEMIDE_OUTBOX_ENABLED=true
ARTEMIDE_OUTBOX_ATTEMPT_CAP=10
ARTEMIDE_OUTBOX_SWEEP_INTERVAL=300
```

The bot token is issued and hashed through Settings → Automation, not hand-written into `.env`; the env var is the fallback for first boot only and should be rotated immediately after.

---

## Constraints & Non-Goals — v1.2

**Explicit non-goals (do not build):**

- **No in-application sending.** Artemide queues and approves; n8n sends. No SMTP client.
- **No auto-approval, ever.** Only an `owner`-role token, acting deliberately, sets a message to `approved`. The bot role is blocked at the service layer.
- **No bulk approval** in v1.2 — one message at a time.
- **No mailbox parsing in Artemide** — n8n reads the bot mailbox and posts structured proposals in.
- **No scoring opacity** — every `fit_score` carries its `fit_breakdown`.
- **No language signalling a personal career search** anywhere in code, DB, logs, or UI.

**Performance budgets (carry v1.1, plus):**

- `/engagements` board initial load p95 < 1.5s at 500 engagements.
- `FitService.rescore_all` < 2s at 500 open engagements.
- Outbox sweep < 500ms per run at 1,000 undelivered events.

---

## Build sequence

Five phases, each independently deployable and testable. Data layer before UI; the message queue and its approval rule are built and tested before any n8n workflow can send anything.

1. **Phase A — Data & profile.** Migrations 012–021, repositories, Pydantic models, FitService with tests.
2. **Phase B — Services, REST, MCP, roles.** All new services, REST routes, MCP tools, and the `auth.py` role enforcement.
3. **Phase C — Outbox & programme.** OutboxService + sweep, ProgrammeService + status, milestones seeded.
4. **Phase D — UI.** Board, orgs, engagement detail, the approval inbox, programme page, dashboard additions.
5. **Phase E — n8n.** The seven workflows + sender, against the bot token, with idempotency.
