# Artemide v1.2 — Claude Code Prompt Sequence

Five phases, one Claude Code session each. The full spec is at `docs/SPEC_v1.2.md`.
Each prompt is directive and self-contained. Every phase ends deployable and testable.

> **Repo reconciliation (this codebase):** migrations are renumbered `012`–`021`
> (v1.1 occupies `001`–`011`); the engagements board ships at `/engagements`
> (`/pipeline` is the v1.1 Outreach pipeline); `auth.py` is rewritten from a single
> actor to token→`api_tokens`→`{actor, role}`.

**Before Phase A:** commit the spec into the repo as `docs/SPEC_v1.2.md` and confirm
the v1.1 codebase runs (`docker compose up -d`, `/health` returns 200).

---

## Phase A — Data & profile

Build the v1.2 data layer only. No services, no API, no UI.

1. Migrations 012–021 per the spec's "Migrations — additions": organisations;
   engagements + engagement_log; engagement_profile (partial unique active index +
   seed row); messages (source_ref unique); events_outbox; programme_milestones
   (+ seed rows); api_tokens (backfill the existing token as actor 'FF' role 'owner');
   rebuild notes with extended CHECK; add contact_log.engagement_id FK; extend FTS5 +
   sync triggers. Forward-only, idempotent on re-run. updated_at triggers for
   organisations, engagements, messages, programme_milestones.
2. Repositories: `src/repository/{orgs,engagements,messages,outbox,engagement_profile,programme,api_tokens}.py` — raw parametrised SQL, v1.1 style.
3. Pydantic models in `src/models.py` for every new entity/request/response.
4. FitService (`src/services/fit_service.py`) per Rule 13.
5. `scripts/seed_engagement_profile.py` and `scripts/seed_milestones.py`.
6. `tests/test_fit_service.py` (hard-fail cap, comp distance, weight application,
   neutral 50 for unknowns).

CONSTRAINTS: no transports/UI this phase; soft delete only; neutral names only.

VERIFY: migrate a fresh `data/artemide.db`; assert tables/indexes + partial unique
active-profile index; run both seeds; `uv run pytest tests/test_fit_service.py` green.

---

## Phase B — Services, REST, MCP, roles

1. Services: OrgsService, EngagementsService, MessagesService, ProgrammeService;
   extend ContactsService.log with optional engagement_id. Explicit actor/transport;
   AuditService.record after every mutation. advance_stage/close write an
   engagement_log row + a clearly-marked emit hook that no-ops (wired in Phase C).
2. Rule 14 stage guard (forward-only + any→closed, 422 on illegal) and Rule 13 scoring
   on upsert/rescore.
3. REST routes (`routes_orgs/engagements/fit/messages/programme`) per the endpoint
   table incl. min-role; 403 uses `{"error":"forbidden_role","message":"..."}`.
4. MCP tools: upsert_org, upsert_engagement, advance_engagement, list_pipeline,
   queue_message, list_messages, approve_message, programme_status. Register them.
5. Rewrite `src/auth.py`: bearer → api_tokens row → request.state.actor/role; enforce
   Rule 18 scopes; Rule 17 approve is owner-only (bot → 403, audited).
6. Tests: test_engagements_service (stage guard), test_messages_service (bot CANNOT
   approve), test_role_scopes (every owner-only endpoint rejects a bot token).

CONSTRAINTS: no outbox consumer/sweep/UI this phase; approve only flips status; the
emit hook is wired in Phase C; Idempotency-Key on all writes.

VERIFY: `uv run pytest tests/` green; `/api/v1/docs` shows new endpoints; bot-token
approve → 403 + audit row.

---

## Phase C — Outbox & programme

1. OutboxService per Rule 19: emit() best-effort/non-blocking; list_undelivered;
   mark_delivered; sweep with attempt cap. Wire the Phase-B hooks for real
   (engagement.surfaced, engagement.stage_changed, message.approved).
2. REST: routes_events (GET /events, POST /events/{ulid}/ack — bot role).
3. ProgrammeService.status() per Rule 16 + days_to_target(); on stage 'offer' flip the
   relevant milestone toward done (Rule 14); Rule 15 reciprocity suggestion.
4. Schedule the sweep as an in-process background task on startup (configurable
   interval). No external scheduler, no inbound ports.
5. Tests: test_outbox_service (at-least-once, dedupe by ulid, attempt cap) + a
   programme-status fixture asserting RAG transitions at the documented thresholds.

VERIFY: outbox + programme tests green; insert→advance→approve shows three event
types in GET /events, ack drops one; GET /programme/status returns RAG + days.

---

## Phase D — UI

Astro 5 / React 19 islands / Tailwind 4. Reuse `web/src/styles/tokens.css` + `ui/`.

1. Pages: `engagements/index.astro` (board), `engagements/[ulid].astro`,
   `orgs/index.astro`, `orgs/[ulid].astro`, `messages.astro`, `programme.astro`. Add
   nav entries + SPA-fallback shells in `src/app.py`.
2. Feature components per the spec list (pipeline/, org/, engagement/, messages/,
   programme/, dashboard/). Fit badge: Slate ≥70, Light Gray 40–69, Dormant Gray +
   flag when hard_fail.
3. `/messages` approval inbox is the priority screen: Approve (Vermillion), Edit
   (inline; save sets 'edited', still needs Approve), Discard. NO bulk approve.
4. Extend `web/src/lib/{types.ts,api.ts}`. Skeleton/EmptyState/ErrorBoundary as v1.1.

CONSTRAINTS: no direct-send control; Approve only flips server state; labels neutral;
Vermillion reserved for primary CTAs and awaiting-approval/overdue accents.

VERIFY: `npm run build` ok; visit the new routes against live API; approve a proposed
message → status flips + message.approved in GET /events.

---

## Phase E — n8n

n8n authenticates with the BOT-role token only. Mail sends from the bot mailbox and
ONLY after Artemide emits message.approved. Claude classifies/drafts; company-data MCP
supplies research.

Build/export `n8n/01_radar.json … 07_rollup.json`, `n8n/sender.json`, each idempotent
(dedupe on Artemide + outbox ULIDs; Idempotency-Key on writes). Write `n8n/README.md`
documenting required credentials (never commit values). The Sender is the ONLY workflow
that sends mail, and ONLY off message.approved; no workflow calls approve.

VERIFY: import each JSON into n8n; end-to-end Cadence → propose → owner approve in UI →
Sender consumes message.approved → mark_sent; Inbound triage twice on the same mail id →
one message (source_ref idempotency); no workflow can approve (bot → 403).

---

## After the build

- Rotate the first-boot bot token immediately (Settings → Automation), then remove
  `ARTEMIDE_N8N_TOKEN` from `.env`.
- Keep `docs/SPEC_v1.2.md` and this prompt file in the repo; keep the confidential plan
  document and the naming decode out of it.
- First real use: seed the org list and partners, let Radar and Cadence run for a week
  with auto-send off at the workflow level, eyeball the proposed drafts, and only then
  wire the Sender live.
