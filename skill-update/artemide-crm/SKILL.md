---
name: artemide-crm
description: >-
  Operate the Artemide executive-search relationship CRM end-to-end from Claude
  Code via its MCP tools (mcp__artemide__*). Use whenever Francesco mentions
  search firms or partners, logging a contact ("I met / emailed / had coffee
  with"), what's due, planning the quarter, auditing the ledger, dormant
  relationships, follow-ups, drafting or sending an outreach, templates, the
  outreach pipeline or stages, OR the v1.2 programme layer: organisations/orgs,
  engagements/mandates/roles-in-motion, the pipeline by fit, fit scores, the
  message approval queue, programme status/RAG/milestones. Also triggers on the
  seeded firm names (Spencer Stuart, Heidrick, Russell Reynolds, Egon Zehnder,
  Korn Ferry, TML Partners, Odgers, MBS, Grace Blue, Eric Salmon, True Search,
  Acertitude, Erevena, Sapphire Partners) and on phrases like "log a contact",
  "what's due", "plan the quarter", "audit the ledger", "draft an outreach to",
  "send the draft", "mark sent", "what stage", "add an org", "surface an
  engagement", "advance the engagement", "what's awaiting approval", "approve
  that message", "programme status", "metrics", "reciprocity", AND the
  compensation layer: comparing packages/scenarios/offers, "total comp",
  "compare the offer", "baseline package", base/bonus/equity/benefits figures.
  Always call a tool for state — never answer relationship, pipeline, or
  compensation state from memory.
---

# artemide-crm

Operate **Artemide** — Francesco's private executive-search relationship CRM —
entirely from Claude Code. All state is read and written through the **`artemide`
MCP server**: 33 tools exposed as **`mcp__artemide__<tool>`**. The tools are
always live; there is no ledger file to paste. Every mutation is audit-logged
server-side and appears in the web UI (`https://artemide.francescofederico.net`,
behind Cloudflare Access — open in a browser to verify visually) immediately.

**Discretion (hard rule).** Artemide is modelled as a neutral *business-development
engagement pipeline*. Never use language that signals a personal job or career
search — not in messages, notes, summaries, commit messages, or anything you
print. Keep everything indistinguishable from a senior operator tracking inbound
mandates.

**Always call a tool for state.** Never answer "your last contact with X was…"
or "the pipeline looks like…" from memory or from this file — call the tool. On
any tool failure, surface the error verbatim and stop; never fabricate state.

---

## ⚠️ Two different "engagement" vocabularies — never confuse them

Two unrelated subsystems both use the word **"engagement."** The wrong tool
writes the wrong table.

| When Francesco means… | Subsystem | Tools |
|---|---|---|
| a row in the **12-month outreach plan / calendar** — a *planned touch* ("the Track 2 podcast pitch", "what should I do this week") | **Engagement *calendar*** (relationship layer) | `list_engagements`, `update_engagement` |
| a **role / mandate in motion at an organisation** ("the CMO role at Acme is at formal stage, fit 82") | **Mandate pipeline** (programme layer) | `upsert_engagement`, `advance_engagement`, `list_pipeline` |

There are likewise **two "pipelines":**
- `pipeline_snapshot` → **partners** bucketed by *outreach stage* (relationship layer).
- `list_pipeline` → **mandates** grouped by *fit/stage* (programme layer).

**Heuristic:** *calendar / plan / touch / track* → `list_engagements` /
`update_engagement`. *Org / role / mandate / fit / the stage of a job* →
`upsert_engagement` / `advance_engagement` / `list_pipeline`. When you can't
tell, **ask which one** before writing.

---

## The 33 tools (call as `mcp__artemide__<name>`)

### A · Relationship ledger — firms, partners, cadence
| Tool | Use |
|---|---|
| `get_partner_state` | Partner profile + firm + recent contact history. **Read before drafting** — it carries `warm_intro_angle`, `thought_leadership`, `practice_focus`. |
| `upsert_partner` | Add a partner at a known firm, or update facts on one. |
| `log_contact` | Record a **real** contact event (organic touches that didn't come from a draft). |
| `list_due_touches` | Partners overdue / due-soon / unscheduled, per tier cadence. |
| `plan_quarter` | Quarterly contact plan: topic + suggested slots + gaps. |
| `set_quarter_topic` | Set/update a quarter's value-exchange topic. |
| `audit_ledger` | Full audit: coverage, dormancy, follow-ups, reciprocity, summary actions. |
| `import_markdown` | One-time v1 ledger import (idempotent). Rarely needed. |

### B · Outreach workspace — calendar, templates, drafts, send
| Tool | Use |
|---|---|
| `list_engagements` | **Calendar** rows; filter `status` / `track` (track-1…6) / `due_window` (past_due/this_week/next_30/next_90/all) / partner / firm. The daily "what should I do" view. |
| `update_engagement` | Patch a calendar row — usually `status: complete` or reschedule `due_date`. |
| `list_templates` | Find a template by `channel` / `category` before drafting. |
| `render_template` | Interpolate a template against a partner → `{subject, body, missing_variables, used_variables}`. Seeds a draft with partner facts. |
| `create_template` | Save a reusable template — **only when Francesco asks**. |
| `list_drafts` | Drafts in flight (partner / status / channel). |
| `get_draft` | Read one draft (head + version count) before updating, so you don't stomp edits. |
| `create_draft` | Save a composed outreach. Empty `body` + `template_ulid` → server renders it. Auto-advances partner `researched → drafted`. |
| `update_draft` | Iterate a draft; bumps version on subject/body change. **Cannot set `sent`.** |
| `mark_sent` | The atomic send-record: writes a `contact_log` row, advances `drafted → sent`, freezes the body in the immutable message log. **Confirm intent first.** |
| `set_outreach_stage` | Move a partner along the Kanban after sent: `replied` / `met` / `ongoing` / `paused` / `dropped` (backwards allowed). |
| `pipeline_snapshot` | **Partners** by outreach stage (filters: tier / strategic_relevance / ned_gateway / track). |
| `outreach_metrics` | Volume by week, response rate, plan-execution %, funnel counts, reciprocity totals. |

### C · Programme & mandate pipeline (v1.2)
| Tool | Use |
|---|---|
| `upsert_org` | Create/update an organisation (`watch_state`, `scale_band`, `sector`, `pertinence_note`). |
| `upsert_engagement` | Create/update a **mandate** at an org (`role_title`, `role_type`, `source`, `source_partner`, comp). Triggers fit scoring. |
| `advance_engagement` | Move a mandate forward a stage. Closing (`to_stage="closed"`) **requires `closed_reason`**. Logs the change + emits an outbox event. |
| `list_pipeline` | **Mandates** grouped by stage, fit score descending. |
| `queue_message` | Propose a draft message → lands as **`proposed`, never sent** (Rule 17). |
| `list_messages` | The approval queue (default `status=proposed`). |
| `approve_message` | Approve (owner-only) → emits `message.approved`. **Confirm first.** See human-gate note. |
| `programme_status` | Per-phase RAG, overall RAG, `target_at_risk`, days-to-target. |

### D · Compensation scenarios (owner-only)
| Tool | Use |
|---|---|
| `upsert_comp_scenario` | Save/update a package scenario (matched by `ulid` or `name`). All money fields are **GBP integers** (annual); `pension_pct` is the employer % of base; `equity_gbp` is annualised expected equity value. Optional `engagement_ulid` links it to a mandate. |
| `list_comp_scenarios` | All saved scenarios, baseline first; returns `baseline_ulid`. Filter by `status`. |
| `compare_comp` | Side-by-side vs the baseline ("Current — S&P Global"). Per field: `delta_gbp` + `delta_pct` (`delta_pct` is null when the baseline component is 0). Omit `scenario_ulids` to compare everything live. |
| `delete_comp_scenario` | Soft-delete a scenario. The baseline can't be deleted — set another baseline first (via the web UI or `POST /{ulid}/baseline`). |

Totals are computed server-side, never stored: `total_cash_gbp = base + cash
bonus`; `total_gbp = total_cash + equity + pension value (base × pct) +
healthcare + car allowance + other`. Scenario `status` vocabulary:
`current` `offer` `negotiating` `accepted` `rejected`.

---

## Roles & the human gate

- Claude Code authenticates with the **owner** token (actor `FF`). Owner can call
  everything, including `approve_message`.
- **All four comp tools are owner-only, reads included** — bot tokens get
  `forbidden_role` on the entire compensation surface (package figures never
  reach the bot role), and each denial is audit-logged.
- **Rule 17 (cardinal):** a queued message is *only ever* created as `proposed`.
  `approve_message` flips it to `approved` and emits `message.approved` to the
  events outbox; an external **n8n** "Sender" workflow is what actually sends mail
  and marks the message sent. **Artemide never sends mail itself.** Approving is
  therefore the *commit* — treat it like one.
- **n8n workflows are currently imported but INACTIVE.** So approving a queued
  message today emits the event but **nothing sends** until the Sender workflow is
  activated. Don't imply a message went out. The live "send" path right now is the
  relationship-layer draft flow below (Francesco sends from his own client, then
  you `mark_sent`).
- **Confirm before** `approve_message`, `mark_sent`, and any delete/restore. You
  are the human in the loop — don't auto-approve your own drafts without giving
  Francesco a beat to glance.

---

## Core workflows

**1 · Log a real contact.** Francesco: "I had coffee with Imogen, shared the
manuscript, she introduced me to a peer at Spencer Stuart." → `get_partner_state`
to resolve the partner ULID if needed, then `log_contact` with channel,
`initiated_by`, `summary`, and `value_given` / `value_received`. Let the service
fire state transitions — don't set `relationship_state` by hand. Echo back what
was recorded.

**2 · Compose & record an outreach (draft → send).**
1. `get_partner_state(partner_ulid)` — pull `warm_intro_angle`,
   `thought_leadership`, `practice_focus`. Don't skip — this is what makes the
   outreach sharp instead of generic.
2. `list_templates(channel=…)` → pick one → `render_template(template, partner)`.
   **Check `missing_variables`** and surface gaps before drafting around them.
3. Refine in conversation, in Francesco's voice.
4. `create_draft(...)` — auto-advances `researched → drafted`. Echo the draft ULID.
5. `update_draft(...)` for each revision (versions are kept).
6. When Francesco says "send it": **confirm**, then `mark_sent(draft_ulid,
   recipient_handle=…)`. Echo: "Recorded sent <date> to <handle>; partner →
   `sent`; last_contact_date updated."

**3 · Engagement *calendar* — "what should I do this week?"**
`list_engagements(due_window="this_week")` then `"next_30"`. Present by track.
Completed → `update_engagement(ulid, {status: "complete"})`. Slipping →
`update_engagement(ulid, {due_date: …})`.

**4 · Partner outreach pipeline.** `pipeline_snapshot()` for the Kanban; filter for
narrower views. Flag partners **stuck at `drafted` > 7 days** ("ready to send when
you are") and **`sent` with no `replied`** within the tier window (follow-up). On
a reply/meeting → `set_outreach_stage(partner, stage=…)`.

**5 · Cadence & audit.** `list_due_touches` for the actionable overdue list;
`audit_ledger` for the full coverage / dormancy / reciprocity report.

**6 · Programme — surface a mandate and move it.**
1. `upsert_org(...)` — the organisation (set `watch_state`, `scale_band`,
   `pertinence_note`). 2. `upsert_engagement(...)` — the role-in-motion; link
   `source_partner` if a partner surfaced it; comp fields drive fit. Fit scores
   automatically. 3. `list_pipeline()` to see it placed by fit. 4.
   `advance_engagement(ulid, to_stage=…, summary=…)` as it moves; to **close**,
   pass `to_stage="closed"` **and** a `closed_reason`. Echo the new stage + fit.

**7 · Message approval queue.** `list_messages()` shows what's proposed. To draft
one programmatically: `queue_message(...)` (lands `proposed`). To approve:
**confirm**, then `approve_message(message_ulid)` — and remind Francesco the Sender
is inactive, so this stages it rather than sends it (today).

**8 · Status & metrics.** `programme_status()` for phase RAG + days-to-target;
`outreach_metrics()` for relationship-side pacing.

---

## Vocabulary — the values that gate valid inputs

- **Partner outreach stage** (Kanban): `researched → drafted → sent → replied →
  met → ongoing → paused → dropped` (you may move backwards).
- **Relationship state** (temperature, don't set directly): `cold` / `warming` /
  `warm` / `dormant`.
- **Contact channel** (`log_contact`): `email` `call` `coffee` `event` `inmail`
  `message` `other`. **Outreach/template channel** (`create_draft`,
  `list_templates`): `email` `linkedin` `message` `other`. `initiated_by`: `me` /
  `them`.
- **Mandate stage** (`advance_engagement`, forward-only + any→closed): `surfaced →
  exploratory → formal → final → offer → decision`, `closed`. **`closed_reason`
  (required to close):** `withdrew` `rejected` `declined_offer` `accepted`
  `lapsed`.
- **Mandate interest:** `pass` `exploratory` `active` `preferred`.
- **Org `watch_state`:** `watch` `target` `active` `parked` `excluded`.
  **`scale_band`:** `fortune_500` `global_equivalent` `pe_backed` `other`.
  **`role_type`:** `cmo` `cmgo` `cco` `transformation` `ned` `other`.
- **Calendar row status:** `not_set` `planned` `in_progress` `complete`.
- **Message** `kind`: `inbound_reply` `cadence_touch` `cold_outreach` `thank_you`
  `custom`; `channel`: `email` `inmail` `message`; `status`: `proposed` `approved`
  `edited` `sent` `discarded`.

Cadence thresholds, the relationship-state machine, fit-scoring weights, and
programme RAG rules are in **`reference.md`** (this folder).

---

## Tool-use discipline

1. **Call the tool before answering any state question.** Don't recite history
   from memory.
2. **Pull intelligence before drafting** (`get_partner_state` / `render_template`).
3. **Never invent firms or partner names.** The seeded firm set is fixed (see
   `reference.md`); confirm anything outside it. If Francesco says "the Heidrick
   partner" without a name, list the seeded Heidrick partners and ask which.
4. **Echo every state change back for verification** — it's the only way Francesco
   catches a mis-resolved ULID at conversation time.
5. **Confirm before commits:** `mark_sent`, `approve_message`, deletes.
6. **Mind the two "engagement" vocabularies** (top of this file) and the two
   "pipelines" on every call.

---

## When tools fail

- **No `mcp__artemide__*` tools available / "not connected"** → the MCP server
  isn't reachable. Check `claude mcp get artemide` (should say ✔ Connected) and
  `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:47600/health` (expect
  200). If the container was recreated, the loopback port should persist; see the
  connection runbook in `reference.md`.
- **401** → bearer token mismatch (the owner token rotated). Stop; surface it.
- **403 `forbidden_role`** → the token resolved to `bot`, not `owner` (
  `approve_message`, deletes, profile edits, token rotation, and **every comp
  scenario tool** are owner-gated). Stop.
- **404 not_found** → stale/wrong ULID. Re-resolve via `get_partner_state` or ask.
- **409 conflict** → e.g. `mark_sent` on an already-sent draft (immutable), or a
  duplicate `create_draft` / `upsert`. Read current state and report it.
- **422 rule_violation** → illegal transition (e.g. skipping a mandate stage, or
  `cold → warm` without `warming`, or closing without `closed_reason`). Don't force
  it; log the underlying event and let the service decide.
- **Timeout / network** → say so, suggest a retry; never fabricate.
