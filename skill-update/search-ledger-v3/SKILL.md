---
name: search-ledger
description: Manages Francesco's executive-search relationship ledger AND outreach workspace via the Artemide MCP server (https://artemide.francescofederico.net). Use whenever Francesco mentions search firms, partners, logging contact, the quarterly value-exchange plan, audit of the relationship asset, dormant relationships, follow-ups, drafting an outreach, templates, the outreach pipeline, the 12-month engagement plan, or analytics. Triggers on "log a contact", "I met with", "I emailed", "had coffee with", "what's due", "plan the quarter", "audit the ledger", "show me my relationship state", "dormant", "follow-up", "warm intro", "draft an email/message/note to", "draft an outreach", "compose to", "send the draft", "mark sent", "template", "render template", "pipeline", "what stage", "move to sent/replied/met", "engagement calendar", "this week's plan", "what's coming up", "metrics", "response rate", "reciprocity", and firm names (Spencer Stuart, Heidrick, Russell Reynolds, Egon Zehnder, Korn Ferry, TML Partners, Odgers, MBS, Grace Blue, Eric Salmon, True, Acertitude, Erevena, Sapphire Partners). Never ask Francesco to upload a markdown ledger — tools are always live; on tool failure surface the error verbatim and stop.
---


> **NOTE FOR INSTALLER:** This is **v3** of the search-ledger skill. The
> description above preserves the v1+v2 trigger surface and adds the
> Phase-11 outreach-workspace triggers. Compare your installed file
> against this one before publishing; v3 adds 13 new MCP tools and a
> drafting → send workflow.

# search-ledger (v3)

## Artemide connection

The ledger is hosted on **Artemide** at
`https://artemide.francescofederico.net`. State is read and written
exclusively through the **21 MCP tools** below; there is no markdown
file to upload anymore. Every mutation is audit-logged server-side and
visible in the UI immediately.

### Tools — original eight (still in use)

| Tool | Use |
|---|---|
| `log_contact` | Record a new contact event with an existing partner (use this for organic touches that don't come from a draft) |
| `upsert_partner` | Add a new partner at a known firm, or update facts on an existing one |
| `get_partner_state` | Fetch a partner's profile + recent contact history |
| `list_due_touches` | Surface partners who are overdue, due-soon, or unscheduled |
| `plan_quarter` | Generate quarterly contact plan (topic + slots + gaps) |
| `set_quarter_topic` | Set or update the value-exchange topic for a quarter |
| `audit_ledger` | Produce the full audit report (coverage, dormancy, follow-ups, reciprocity, summary actions) |
| `import_markdown` | (One-time migration only) ingest a v1 markdown ledger; idempotent |

### Tools — Phase-11 outreach workspace (13 new)

**12-month engagement calendar** (the 30 seeded outreach plan entries)

| Tool | Use |
|---|---|
| `list_engagements` | List entries from the 12-month plan. Filter by `status`, `track` (`track-1`…`track-6`), `due_window` (`past_due`/`this_week`/`next_30`/`next_90`/`all`), `partner_ulid`, or `firm_ulid`. Use as Francesco's daily/weekly "what should I be doing" view. |
| `update_engagement` | Patch an engagement entry. Most common: bump status to `complete` (after Francesco executes it) or change `due_date` to reschedule. |

**Templates** (reusable scaffolds with `{{partner.name}}` / `{{partner.warm_intro_angle}}` / etc.)

| Tool | Use |
|---|---|
| `list_templates` | Find a template before drafting. Filter by `channel` (`email`/`linkedin`/`message`/`other`) or `category` (`cold_intro`, `warm_followup`, `thought_share`, `reciprocity`, freeform). |
| `render_template` | Render a template against a specific partner. Returns `{subject, body, missing_variables, used_variables}`. The body is fully interpolated; you then refine. Use this to *seed* your composition with partner-specific facts. |
| `create_template` | Save a new reusable template after Francesco explicitly asks to save one. Don't do this proactively. |

**Drafts** (the workspace where outreach is composed before send)

| Tool | Use |
|---|---|
| `list_drafts` | What's currently in flight? Filter by `partner_ulid` / `status` (`draft`/`ready`/`sent`/`archived`) / `channel`. |
| `get_draft` | Read one draft (head + version count). Use before updating to avoid stomping on Francesco's manual edits. |
| `create_draft` | Save a freshly-composed outreach. If `body` is empty and `template_ulid` is given, the server interpolates the template against the partner. Auto-advances `partner.outreach_stage` `researched` → `drafted`. |
| `update_draft` | Iterate on an existing draft. Bumps the version automatically if `subject` or `body` changes (versions are kept in history). **You can't set status to `sent` here — that's `mark_sent`'s job.** |
| `mark_sent` | The atomic send: records that Francesco hit send, writes a `contact_log` entry (with `initiated_by=me` and the body excerpt as summary), updates `partner.last_contact_date`, freezes the message in `outreach_message`, and advances `partner.outreach_stage` `drafted` → `sent`. **All in one transaction.** Idempotent on retry with the same `draft_ulid` (the second call returns 409). |
| `set_outreach_stage` | Move a partner along the Kanban after `sent`. Valid stages: `researched`, `drafted`, `sent`, `replied`, `met`, `ongoing`, `paused`, `dropped`. Use this when Francesco reports a reply, a meeting, or pauses. |

**Pipeline + analytics**

| Tool | Use |
|---|---|
| `pipeline_snapshot` | Returns partners bucketed by `outreach_stage`. Filter by `tier`, `strategic_relevance`, `ned_gateway`, `track`. Useful for "what does the pipeline look like?" / "who's stuck at drafted?". |
| `outreach_metrics` | Aggregate dashboard data — outreach volume by week, response rate, plan-execution %, pipeline funnel counts. Use when Francesco asks how he's pacing. |

## Firm directory

**Fourteen firms** are seeded (12 core London CMO ecosystem firms + 2 additional for NED-focused partners). **Never invent firms outside this list** — confirm before treating anything else as canonical.

### Primary tier — Tier-1 global

- **Spencer Stuart** (Global, cold) — Largest dedicated CMO franchise. Publishes the CMO Tenure Study. Top priority for warm introduction.
- **Heidrick & Struggles** (Global, cold) — Deepest single-partner CMO pedigree via Richard Sumner. Heidrick Leadership Podcast, CMO Barometer, CAG Moves newsletter.
- **Russell Reynolds** (Global, cold) — Greg Hodge leads CMO UK. Tristan Jervis covers tech/AI. Laura Sanderson is the NED gateway. 'The New CEO' book overlap.
- **Egon Zehnder** (Europe, cold) — Strongest NED practice. Miranda Pode for FS CMO. Karoline Vinsrygg + Çağla Bekbölet for board/NED gateway.
- **Korn Ferry** (Global, cold) — Grant Duncan is the single highest-priority contact in the entire ecosystem. KF Architect comp database. Modern Marketer report.

### Specialist tier — specialist boutique

- **TML Partners** (London, **warm**) — Marketing-leadership-only boutique. **Only existing warm tie.** Simon Bassett (Managing Partner). Annabel Venner (NED + Marketing Society Fellows + potential book endorser). The CMO Report.
- **Odgers Berndtson** (London, cold) — Mark Freebairn leads NED/Board. Virginia Bottomley chair-level NED.
- **MBS Group** (London, cold) — Consumer-leaning. Lower priority given B2B focus.
- **Grace Blue Partnership** (London, cold) — Agency-CMO specialist. Jay Haines (AI/agency-crossover via Sinecure). Sarah Skinner (brand transformation).
- **True Search** (Global, cold) — Tech-leaning; SaaS / fintech scale-up.
- **Eric Salmon & Partners** (Europe, cold) — Italian heritage, European optionality.
- **Acertitude** (Global, cold) — PE-backed mid-market.

### Honourable-mention tier (NED specialists)

- **Erevena** (London, cold) — Tech/scale-up. Flo Bown (CMO practice).
- **Sapphire Partners** (London, cold) — NED + FTSE board-composition specialist. Kate Grussing CBE.

## Twenty-eight seeded partners (intelligence available)

For each partner the ledger holds rich intelligence: **`warm_intro_angle`** (the specific actionable intro route), **`thought_leadership`** (their published pieces / data products), **`practice_focus`** (their specialism), **`strategic_relevance`** (`HIGH`/`MEDIUM`/`LOW`), **`ned_gateway`** (boolean — gates Francesco's NED-track ambitions), and **`prior_career`**. **Always read these fields before drafting** — they are the difference between a generic outreach and a sharp one.

Use `get_partner_state` to fetch them, or `render_template` (which already pulls them into the interpolation context).

The **six engagement tracks** the seeded plan organises around:

| Track | Window | Focus |
|---|---|---|
| Track 1 | 0–90d | RRA (Greg Hodge) + TML follow-up (Simon Bassett, Annabel Venner) |
| Track 2 | 0–90d | Heidrick (Richard Sumner podcast pitch; Kit Bingham EPOC Network) |
| Track 3 | 90–180d | Spencer Stuart (Emanuela Aureli via AESC / TMT angle) |
| Track 4 | 90–180d | Korn Ferry (Grant Duncan — Marketing Society / IPA bridge; Modern Marketer co-content) |
| Track 5 | 180–270d | NED portfolio (Karoline Vinsrygg, Kit Bingham, Laura Sanderson, Mark Freebairn, Kate Grussing) |
| Track 6 | 180–360d | Book v2 launch co-content + conferences (Cannes Lions, Gartner London, Marketing Society Global, Festival of Marketing) |

## Drafting workflow (the core new flow)

When Francesco says **"draft an outreach to [partner]"** or **"compose to [partner]"** or similar:

1. **`get_partner_state(partner_ulid)`** — pull the partner's full profile including `warm_intro_angle`, `thought_leadership`, `practice_focus`. Don't skip this. Without it the draft is generic.
2. **`list_templates(channel='email')`** (or LinkedIn, depending on Francesco's hint) — pick a template that matches the situation (cold intro, warm follow-up, thought-piece share, reciprocity ask, etc.).
3. **`render_template(template_ulid, partner_ulid)`** — get the interpolated starting point. **Check `missing_variables` in the response** — if there are any, surface them to Francesco before drafting around the gaps.
4. **Refine in conversation.** Use the rendered text as the scaffold; rewrite with Francesco's voice, his specific recent context, and any framing the warm_intro_angle suggests.
5. **`create_draft(partner_ulid, channel, subject, body, template_ulid)`** — save it. This auto-advances stage to `drafted`. Echo the draft ULID back so Francesco can reference it.
6. **Iterate via `update_draft(draft_ulid, body=...)`** for each revision Francesco asks for. Each save bumps the version (kept in history).
7. **When Francesco says "send it" or "mark sent":** call **`mark_sent(draft_ulid, recipient_handle=...)`**. This is the all-or-nothing transaction that creates the contact_log entry, advances the partner's stage, and freezes the body. Confirm back: "Logged as sent on 2026-05-15 to greg@example.com. Partner stage → sent."

**Don't pre-emptively skip a step.** If Francesco asks "draft and send", still create the draft first; then `mark_sent` against that draft_ulid. The two-step flow gives him a chance to glance.

## Stage advancement (Rule 2 — Phase 11)

`outreach_stage` is the **Kanban axis** and is separate from `relationship_state` (which captures emotional temperature: cold/warming/warm/dormant). Both move in parallel.

Auto-advance happens here:
- `researched → drafted` — when `create_draft` is called.
- `drafted → sent` — when `mark_sent` succeeds.

Everything beyond `sent` is **manual**. Call `set_outreach_stage`:
- **They replied** → `replied`.
- **You had the meeting / call** → `met`.
- **Ongoing dialogue (multiple exchanges)** → `ongoing`.
- **Lull, by design** → `paused`.
- **Not worth pursuing further** → `dropped`.

Going *backwards* is allowed (e.g., a `sent` partner ghosted → pause to `paused`, or drop to `dropped`).

## Engagement-calendar workflow

The 12-month plan is the strategic frame. When Francesco asks **"what should I be doing this week / next 30 days?"**:

1. **`list_engagements(due_window='this_week')`** (or `'next_30'`) — returns the rows for that window.
2. Present them by track. Tracks 1+2 are the warm-up. Tracks 3+4 kick in around day 90. Track 5 is NED-focused. Track 6 is book v2 + conferences.
3. When Francesco completes one: **`update_engagement(ulid, update={status: 'complete'})`**. Echo back the percentage of the next-30 window now complete.
4. When something needs to slip: **`update_engagement(ulid, update={due_date: '...'})`**.

The dashboard `plan-execution` metric tracks this — Francesco can see his pacing against the plan.

## Pipeline visibility

When Francesco asks **"pipeline?"** or **"who's stuck where?"**:

- `pipeline_snapshot()` for the full Kanban (all 8 stages always returned).
- Filter with `tier=primary`, `strategic_relevance=HIGH`, or `ned_gateway=true` for narrower views.
- Look for **partners stuck at `drafted` >7 days** — those are stalled. Surface them as "ready to send when you are".
- Look for **partners at `sent` with no `replied` within tier window** — those need a follow-up Francesco may have forgotten.

`outreach_metrics()` is the dashboard equivalent.

## Ledger schema (server-side, for context)

- **Firm**: ulid, name, tier (`primary` / `specialist` / `ned`), region, relationship_state (`cold` / `warming` / `warm` / `dormant`), notes_summary, **market_tier** (`tier-1-global`/`specialist-boutique`/`honourable-mention`), **strategic_fit** (`HIGH`/`MEDIUM`/`LOW`), **ned_practice_strength**, **hq_address**, **sectors**, **cmo_practice_depth**, **comp_transparency**, **candidate_reputation**, **b2b_fs_reputation**.
- **Partner**: ulid, firm, name, title, practice, seniority, location, introduced_via, email, linkedin_url, relationship_state, last_contact_date, next_touch_date, next_touch_topic, follow_ups_outstanding (JSON array), **practice_focus**, **strategic_relevance**, **warm_intro_angle**, **thought_leadership**, **prior_career**, **ned_gateway**, **outreach_stage**.
- **Contact**: ulid, partner, contact_date, channel (`email` / `call` / `coffee` / `event` / `inmail` / `message` / `other`), initiated_by (`me` / `them`), summary, value_given, value_received, follow_up.
- **Template**: ulid, name, category, channel, subject_template, body_template, description, soft-deletable.
- **Outreach draft**: ulid, partner, template, channel, subject, body, status (`draft`/`ready`/`sent`/`archived`), version, sent_message_id (set after send).
- **Outreach message** (immutable send log): ulid, draft, partner, contact_log_id, sent_at, sent_via, recipient_handle, subject_snapshot, body_snapshot, version_sent.
- **Engagement calendar**: ulid, firm, partner, due_date, title, description, status, track.
- **Value calendar** (quarterly topic planner — separate from engagement_calendar): year, quarter, topic, status.
- **Notes**: free-form, attached to firm or partner.
- **Audit log**: every mutation, every transport, before/after JSON. Phase-11 actions: `draft`, `send`, `template`, `stage` (in addition to v1's `create`, `update`, `delete`, `restore`, `log_contact`, `import`, `note`, `plan`, `rotate_token`).

## Cadence rules (unchanged from v2)

| Tier | Ideal | Overdue | Dormancy |
|---|---|---|---|
| Primary | 90 d | 120 d | 180 d |
| Specialist | 180 d | 240 d | 365 d |
| NED | — | — | — (deferred) |

`list_due_touches` enforces these. `audit_ledger`'s "Dormant relationships" section flags partners past the dormancy threshold.

## Relationship-state transitions (Rule 1 — unchanged)

- `cold → warming` — automatic when a contact is logged with `advance_state=true` AND value is exchanged AND the firm is still cold.
- `warming → warm` — automatic after three substantive reciprocal contacts (value_given ≥ 1 and value_received ≥ 1 across history).
- Any → `dormant` — manual on firms; on partners, surfaced via audit when last_contact_date crosses the tier dormancy threshold.
- `dormant → warming` — automatic on next logged contact.

Don't try to set partner relationship_state directly — log the contact (or call `mark_sent`, which writes a contact_log entry) and let the service rule fire.

## Operating philosophy (extended)

- **The asset is the relationships, not the activity.** Reciprocity matters. `outreach_metrics` and `audit_ledger` both report reciprocity imbalances.
- **Cadence is a floor, not a ceiling.** Touching primary tier more often than 90d is fine; less often than 120d is a problem.
- **Specialist tier is for optionality** — depth over frequency.
- **NED is a future track** but Track 5 of the engagement plan is starting to seed it (Karoline Vinsrygg, Laura Sanderson, Mark Freebairn, Kate Grussing CBE, Kit Bingham). Use NED gateways carefully.
- **Every contact is a deliberate act, never a metric to hit.** If Francesco hasn't actually had the contact, don't log it. Same for `mark_sent` — don't call it speculatively.
- **Drafts are cheap; sends are not.** It's fine to have 5 drafts in flight per partner if Francesco wants iterations. `mark_sent` is the commit — confirm intent before calling it.

## Common operations

| Francesco says | You call |
|---|---|
| "I had coffee with Imogen yesterday — shared the manuscript, she introduced me to a peer at Spencer Stuart" | `log_contact` |
| "Draft an outreach to Greg Hodge using the Chicago Booth angle" | `get_partner_state` → `list_templates(channel='email')` → `render_template` → refine → `create_draft` |
| "Tighten the second paragraph" | `update_draft(draft_ulid, body=...)` |
| "Send it." (referring to the draft we just iterated on) | `mark_sent(draft_ulid, recipient_handle=...)` |
| "Greg replied. We're talking next Tuesday." | `set_outreach_stage(partner_ulid, stage='replied')` — and offer to log_contact for the reply too if Francesco wants the trail |
| "Plan Q2 / what's coming up in the next two weeks?" | `list_engagements(due_window='this_week')` then `list_engagements(due_window='next_30')` |
| "Mark the Track 2 podcast pitch as done" | `update_engagement(ulid, update={status: 'complete'})` |
| "Push the Spencer Stuart touch to next Friday" | `update_engagement(ulid, update={due_date: '...'})` |
| "What's the pipeline look like?" | `pipeline_snapshot()` |
| "How am I pacing?" | `outreach_metrics()` |
| "Audit the ledger" | `audit_ledger` (unchanged from v2) |
| "What's the relationship state with Sarah Whitfield?" | `get_partner_state` |
| "Save this as a template for cold intros to senior partners" | `create_template` (and confirm the name + variables back) |
| "Add a new partner at TML — …" | `upsert_partner` |

For long-form notes that don't belong in a contact summary, point Francesco at the UI: `https://artemide.francescofederico.net/notes`. Note creation isn't currently an MCP tool.

## Tool-use discipline

1. **Always call the tool before answering state questions.** Don't answer "your last contact with Sarah was…" from memory; call `get_partner_state`.
2. **Always pull intelligence before drafting.** `get_partner_state` (or `render_template`, which fetches the same context) — the `warm_intro_angle` and `thought_leadership` fields are the entire point of the seeded dataset.
3. **Never invent partner names.** If Francesco refers to "the Heidrick partner" without naming them, list the four seeded Heidrick partners (Sumner, Robinson, Bingham, Hibbert) and ask which.
4. **Echo state changes back for verification.** After `mark_sent` succeeded, summarise: "Logged as sent: 2026-05-15 email to Greg Hodge (greg@example.com). Subject: 'Chicago Booth alumni + CMO mandate shift'. Body excerpt: '…'. Partner stage → sent, last_contact_date → 2026-05-15."
5. **Confirm before `mark_sent`.** Unless Francesco has just said "send it" in this turn, ask: "ready to mark this sent?" Send is the only step that creates an immutable contact_log row.
6. **On MCP unreachable: surface plainly.** Quote the error message. Don't paper over it with a guess. Suggest Francesco check `https://artemide.francescofederico.net/health` and the bearer token.
7. **Don't ask Francesco to upload anything.** The ledger is live. If you find yourself drafting a markdown export, stop — that's the v1 workflow.

## When the tools fail

- **401** from any tool → bearer token mismatch. Stop. Surface the error.
- **404 "partner not found"** → the partner_ulid is stale or wrong. Call `get_partner_state` with what you do know, or ask Francesco for the correct name.
- **422 "rule_violation"** → an illegal state transition (e.g. `cold → warm` skipping `warming`, or partner restore blocked by deleted firm). Log a contact instead and let the service decide.
- **409 "conflict"** on `mark_sent` → the draft was already sent (it's immutable). Pull `get_draft` and report the sent state to Francesco.
- **409 "conflict"** on `create_draft` create-vs-collision → re-check whether a draft already exists for that partner+channel via `list_drafts`.
- **400 "validation_error"** on `mark_sent` with a backdated `sent_at` → can't backdate more than 7 days. Use today's date or ask Francesco.
- **Timeout / network error** → say so; suggest a retry. Don't fabricate.
