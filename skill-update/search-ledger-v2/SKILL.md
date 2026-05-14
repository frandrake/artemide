---
name: search-ledger
version: 2
description: |
  Manages Francesco's executive-search relationship ledger via the
  Artemide MCP server. Use when Francesco mentions search firms,
  partners (people, not the firms), logging contact, the quarterly
  value-exchange plan, audit of the relationship asset, dormant
  relationships, or follow-ups due. Triggers on phrases such as:
  "log a contact", "I met with", "I emailed", "had coffee with",
  "what's due", "plan the quarter", "audit the ledger", "show me my
  relationship state", "dormant", "follow-up", "warm intro", "Spencer
  Stuart", "TML Partners", "Egon Zehnder", "Heidrick", "Korn Ferry",
  "Russell Reynolds", "Odgers", "MBS", "True Search", "Eric Salmon",
  "Acertitude". When in doubt, prefer calling a tool over guessing.

  Tools are always live — never ask Francesco to upload, paste, or
  attach a markdown ledger. If a tool fails, surface the error
  verbatim and stop; do not fabricate state.
---

> **NOTE FOR INSTALLER:** This is v2 of the search-ledger skill. The
> description above preserves the v1 trigger surface; before publishing
> compare the trigger phrases line-by-line against your v1 file and add
> back anything I missed. Body content can be edited freely.

# search-ledger (v2)

## Artemide connection

The ledger is hosted on **Artemide** at
`https://artemide.francescofederico.net`. State is read and written
exclusively through the eight MCP tools below; there is no markdown
file to upload anymore.

| Tool | Use |
|---|---|
| `log_contact` | Record a new contact event with an existing partner |
| `upsert_partner` | Add a new partner at a known firm, or update facts on an existing one |
| `get_partner_state` | Fetch a partner's profile + recent contact history |
| `list_due_touches` | Surface partners who are overdue, due-soon, or unscheduled |
| `plan_quarter` | Generate quarterly contact plan (topic + slots + gaps) |
| `set_quarter_topic` | Set or update the value-exchange topic for a quarter |
| `audit_ledger` | Produce the full audit report (coverage, dormancy, follow-ups, reciprocity, summary actions) |
| `import_markdown` | (One-time migration only) ingest a v1 markdown ledger; idempotent |

Every mutation is audit-logged server-side. The UI at
`https://artemide.francescofederico.net` reflects state changes
immediately; Francesco can verify visually any time.

## Firm directory

Eleven firms are seeded. **Never invent firms outside this list** — if
Francesco mentions a firm not below, confirm before treating it as
canonical.

### Primary tier — 90 / 120 / 180-day cadence

- **Spencer Stuart** (Global, cold) — Largest CMO franchise globally.
  Top priority for warm introduction.
- **Heidrick & Struggles** (Global, cold) — Strong B2B CMO franchise.
  Transformation-anchored.
- **Russell Reynolds** (Global, cold) — Strong on transformation CMO
  mandates. Tech and FS overweight.
- **Egon Zehnder** (Europe, cold) — Strongest in continental Europe.
  Chair-track useful for NED.
- **Korn Ferry** (Global, cold) — Useful for comp benchmarking. Broad
  coverage.

### Specialist tier — 180 / 240 / 365-day cadence

- **TML Partners** (London, **warm**) — Marketing leadership
  specialist. Only existing warm tie. Primary entry route for
  cross-introductions.
- **Odgers Berndtson** (London, cold)
- **MBS Group** (London, cold) — Consumer-leaning. Lower priority given
  B2B focus.
- **True Search** (Global, cold) — Tech-leaning. Relevant for
  enterprise SaaS optionality.
- **Eric Salmon & Partners** (Europe, cold) — Italian heritage
  relevant. European optionality.
- **Acertitude** (Global, cold) — Emerging mid-market. PE portfolio
  CMO mandates.

### NED tier

NED-track firms are deferred until the primary + specialist tiers are
healthy. Don't push into NED unless Francesco asks explicitly.

## Ledger schema (server-side, for context)

- **Firm**: ulid, name, tier (`primary` / `specialist` / `ned`), region,
  relationship_state (`cold` / `warming` / `warm` / `dormant`),
  notes_summary.
- **Partner**: ulid, firm, name, title, practice, seniority, email,
  linkedin_url, relationship_state, last_contact_date,
  next_touch_date, next_touch_topic, follow_ups_outstanding (JSON
  array).
- **Contact**: ulid, partner, contact_date, channel (`email` / `call` /
  `coffee` / `event` / `inmail` / `message` / `other`), initiated_by
  (`me` / `them`), summary, value_given, value_received, follow_up.
- **Value calendar**: year, quarter, topic, status (`not_set` /
  `planned` / `in_progress` / `complete`).
- **Notes**: free-form, attached to firm or partner, chronological.
- **Audit log**: every mutation, every transport (REST / MCP / CLI),
  before / after JSON.

## Cadence rules

| Tier | Ideal | Overdue | Dormancy |
|---|---|---|---|
| Primary | 90 d | 120 d | 180 d |
| Specialist | 180 d | 240 d | 365 d |
| NED | — | — | — (deferred) |

`list_due_touches` uses these thresholds. `audit_ledger`'s "Dormant
relationships" section flags partners past the dormancy threshold.

## State transitions (Rule 1)

- `cold → warming` — happens automatically when a contact is logged
  with `advance_state=true` **and** value is exchanged (given or
  received) **and** the firm itself is still cold.
- `warming → warm` — happens automatically once three substantive,
  reciprocal contacts have accumulated (value_given ≥ 1 and
  value_received ≥ 1 across history).
- Any → `dormant` — manual on firms; on partners, surfaced via audit
  when last_contact_date crosses the tier dormancy threshold.
- `dormant → warming` — happens on next logged contact.

Don't try to set partner state directly — log the contact with the
right value fields and `advance_state=true` and let the service rule
fire.

## Value-exchange calendar (current seed)

- **Q1 2026** — Foundational outreach: warm-tie briefs across primary
  tier (status: complete).
- **Q2 2026** — Agentic CMO themes: chapter previews for the v2
  manuscript launch (status: in_progress).
- **Q3 2026** — Mid-year reciprocity review and re-engagement of
  dormant ties (status: planned).
- **Q4 2026** — Year-end outlook calls and NED-track exploration
  (status: planned).

`plan_quarter` returns suggested partner slots spaced across the 13
weeks of the requested quarter, anchored to the topic.

## Operating philosophy

- The asset is the relationships, not the activity. Reciprocity
  matters; one-sided value-giving is logged as a reciprocity imbalance
  in `audit_ledger`.
- Cadence is a floor, not a ceiling. Touching primary tier more often
  than the 90-day ideal is fine; touching less often than the 120-day
  overdue threshold is a problem.
- Specialist tier is for optionality — depth over frequency.
- NED is a future track; we don't fish proactively.
- Every contact is a deliberate act, never a metric to hit. If
  Francesco hasn't actually had the contact, don't log it.

## Common operations

| Francesco says | You call |
|---|---|
| "I had coffee with Imogen yesterday — shared the manuscript draft, she introduced me to a peer at Spencer Stuart" | `log_contact` (partner_ulid resolved via prior context or `get_partner_state`) |
| "Plan Q2" | `plan_quarter(year=2026, quarter=2)` |
| "What's on my plate next two weeks?" | `list_due_touches(window_days=14)` |
| "What's the relationship state with Sarah Whitfield?" | `get_partner_state` |
| "Audit the ledger" / "How am I doing on coverage?" | `audit_ledger` |
| "Where are the gaps?" | `audit_ledger` first; `list_due_touches` if Francesco wants the actionable list |
| "Set Q2 topic to …" | `set_quarter_topic` |
| "Add a new partner at TML — …" | `upsert_partner` |

For long-form notes that don't belong in a contact summary, point
Francesco at the UI: `https://artemide.francescofederico.net/notes`.
Note creation isn't currently an MCP tool.

## Tool-use discipline

1. **Always call the tool before answering state questions.** Don't
   answer "your last contact with Sarah was…" from memory; call
   `get_partner_state`.
2. **Never invent partner names.** If Francesco refers to "the
   Heidrick partner" without naming them, call `get_partner_state` for
   the partner Francesco has already met at that firm, or ask.
3. **Echo state changes back for verification.** After `log_contact`
   succeeded, summarise what was recorded: "Logged: 2026-05-13 coffee
   with Imogen Carr at TML Partners. Value-given: chapter draft.
   Value-received: intro to Sarah Whitfield. Partner state advanced
   cold → warming." This is the only way Francesco can spot a
   mismatched ULID at conversation time.
4. **On MCP unreachable: surface plainly.** Quote the error message.
   Don't paper over it with a guess. Suggest Francesco check
   `https://artemide.francescofederico.net/health` and the Bearer token
   if applicable.
5. **Don't ask Francesco to upload anything.** The ledger is live. If
   you find yourself drafting a markdown export, stop — that's the v1
   workflow.

## When the tools fail

- 401 from any tool → bearer token mismatch. Stop. Surface the error.
- 404 "partner not found" → the partner_ulid Claude used is stale or
  wrong. Call `get_partner_state` with what Claude does know, or ask
  Francesco for the correct name.
- 422 "rule_violation" → an illegal state transition (e.g.
  cold → warm without going through warming). Log a contact instead;
  let the service decide.
- Timeout / network error → say so; suggest a retry. Don't fabricate.
