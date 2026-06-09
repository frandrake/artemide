# artemide-crm — reference

Loaded on demand by the `artemide-crm` skill. Detail that doesn't need to sit in
the main file: the seeded firm directory, entity schemas, cadence/state/fit/RAG
rules, and the connection runbook.

---

## Seeded firm directory (the canonical set — never invent outside it)

There is **no `list_firms` MCP tool**; firms are managed via the UI/REST. Treat
this as the known seed and confirm against the UI (`/firms`) if unsure. Fetch
partner intelligence live with `get_partner_state` — don't rely on names here.

**Primary tier (90/120/180-day cadence):**
- **Spencer Stuart** — largest CMO franchise; CMO Tenure Study. Top warm-intro target.
- **Heidrick & Struggles** — deep CMO pedigree (Richard Sumner); CMO Barometer.
- **Russell Reynolds** — Greg Hodge (CMO UK), Tristan Jervis (tech/AI), Laura Sanderson (NED gateway).
- **Egon Zehnder** — strongest NED practice; Miranda Pode, Karoline Vinsrygg, Çağla Bekbölet.
- **Korn Ferry** — Grant Duncan (highest-priority single contact); KF Architect comp data.

**Specialist tier (180/240/365-day cadence):**
- **TML Partners** — marketing-leadership boutique. **Only existing warm tie.** Simon Bassett, Annabel Venner.
- **Odgers Berndtson** — Mark Freebairn (NED/Board), Virginia Bottomley.
- **MBS Group** — consumer-leaning; lower priority (B2B focus).
- **Grace Blue Partnership** — agency/CMO; Jay Haines, Sarah Skinner.
- **True Search** — tech / SaaS / fintech scale-up.
- **Eric Salmon & Partners** — Italian heritage, European optionality.
- **Acertitude** — PE-backed mid-market.

**NED specialists (honourable mention):**
- **Erevena** — tech/scale-up; Flo Bown.
- **Sapphire Partners** — NED + FTSE board composition; Kate Grussing CBE.

The six engagement-calendar tracks: T1 RRA + TML follow-up (0–90d) · T2 Heidrick
(0–90d) · T3 Spencer Stuart (90–180d) · T4 Korn Ferry (90–180d) · T5 NED portfolio
(180–270d) · T6 book v2 + conferences (180–360d).

---

## Entity schemas (server-side)

- **Firm** — ulid, name, tier (`primary`/`specialist`/`ned`), region,
  relationship_state, notes_summary, market_tier, strategic_fit, ned_practice_strength,
  hq_address, sectors, cmo_practice_depth, comp_transparency, candidate_reputation,
  b2b_fs_reputation. Soft-deletable.
- **Partner** — ulid, firm, name, title, practice, seniority, location, introduced_via,
  email, linkedin_url, relationship_state, last_contact_date, next_touch_date,
  next_touch_topic, follow_ups_outstanding (JSON), practice_focus, strategic_relevance
  (HIGH/MEDIUM/LOW), warm_intro_angle, thought_leadership, prior_career, ned_gateway
  (bool), outreach_stage. Soft-deletable.
- **Contact** — ulid, partner, contact_date, channel, initiated_by, summary,
  value_given, value_received, follow_up, (optional) engagement_id.
- **Template** — ulid, name, category, channel, subject_template, body_template,
  description. Mustache-lite vars (`{{partner.name}}`, `{{partner.warm_intro_angle}}`…).
- **Outreach draft** — ulid, partner, template, channel, subject, body, status
  (draft/ready/sent/archived), version, sent_message_id.
- **Outreach message** (immutable send log) — ulid, draft, partner, contact_log_id,
  sent_at, sent_via, recipient_handle, subject_snapshot, body_snapshot, version_sent.
- **Engagement *calendar*** — ulid, firm, partner, due_date, title, description, status, track.
- **Value calendar** (quarterly topics; separate) — year, quarter, topic, status.
- **Organisation** (v1.2) — ulid, name, sector, scale_band, hq_region, pertinence_note,
  watch_state, source, external_refs (JSON). Soft-deletable.
- **Engagement / mandate** (v1.2) — ulid, org, role_title, role_type, source,
  source_partner_id, stage, interest, comp_base_gbp, comp_total_gbp, comp_equity_note,
  fit_score (0–100), fit_breakdown (JSON), next_step, next_step_date, closed_reason.
  Soft-deletable.
- **Engagement log** (append-only) — engagement, event_date, event_type
  (stage_change/interview/reference/offer/note/withdrawal), from_stage, to_stage, summary.
- **Engagement profile** (fit criteria; one active) — version, comp_base_floor_gbp,
  comp_total_target_gbp, accepted_role_types, accepted_scale_bands, hard_exclusions,
  weights (JSON, sum 100).
- **Message** (v1.2 queue) — ulid, kind, partner, engagement, channel, recipient_hint,
  subject, body, rationale, status, source_ref, created_by_transport, approved_at, sent_at.
- **Events outbox** (append-only) — ulid, event_type, entity, payload, delivered_at,
  delivery_attempts. n8n dedupes on the ulid.
- **Programme milestone** — phase (build/seed/run/close/exit), label, target_date,
  status (pending/on_track/at_risk/done), metric_note.
- **Audit log** — every mutation: actor, transport, action, before/after JSON.

---

## Cadence & the relationship-state machine

| Tier | Ideal | Overdue | Dormancy |
|---|---|---|---|
| Primary | 90 d | 120 d | 180 d |
| Specialist | 180 d | 240 d | 365 d |
| NED | — | — | — (deferred) |

`list_due_touches` enforces these; `audit_ledger` flags partners past dormancy.

State transitions (let the service fire them — never set `relationship_state` directly):
- `cold → warming` — auto when a contact is logged with `advance_state=true`, value is
  exchanged, and the firm is still cold.
- `warming → warm` — auto after three substantive reciprocal contacts (value_given ≥ 1
  and value_received ≥ 1 across history).
- `any → dormant` — manual on firms; surfaced via audit on partners past the threshold.
- `dormant → warming` — auto on the next logged contact.

`outreach_stage` (the Kanban) is a separate axis from `relationship_state` (temperature);
both move in parallel. Auto-advances: `researched → drafted` (on `create_draft`),
`drafted → sent` (on `mark_sent`). Everything past `sent` is manual via `set_outreach_stage`.

---

## Fit scoring (Rule 13) — what `upsert_engagement` computes

Scored against the one active **engagement profile** (seed: base floor £250k, total
target £500k; accepted roles cmo/cmgo/cco/transformation; accepted scale bands
fortune_500/global_equivalent).

1. **Hard filters (gate).** Fail if: role_type not accepted; org scale_band not accepted;
   any org/engagement tag in `hard_exclusions` (`custodial_brand_only`, `high_politics`,
   `micromanaging_board`, `performative_visibility`, `weak_transformation`); or known
   `comp_base_gbp` below the floor. A hard fail sets `hard_fail=true` and **caps the score
   at 39** (sorts below soft-scored rows) — it never deletes or hides the row.
2. **Soft score (weighted, default weights sum 100):** role_type 20, scale 15, comp 20,
   pertinence 15, geography 10, autonomy_signal 10, politics_signal 10. `comp` scores on
   distance to the £500k target (100 at/above). `politics_signal` is inverse. Unknown
   dimensions score 50 (neutral). Weights live in the profile — retuning needs no code.

Every `fit_score` carries its `fit_breakdown`. Re-score after profile edits with the
REST `/fit/rescore-all` (owner) or per-engagement rescore.

## Programme status (Rule 16) — what `programme_status` returns

Per-phase `green/amber/red` + overall + `target_at_risk`, working back from
`ARTEMIDE_PROGRAMME_TARGET_DATE` (2027-04-05):
- **Seed** green if ≥5 partners `warm`/`warming` by the seed milestone; amber 3–4; red <3.
- **Run** green if ≥2 mandates at `formal`/`final` by the run milestone; amber 1; red 0.
- **Close** green if ≥1 mandate at `offer`/`decision` by 12 days before target; else red.
- `target_at_risk=true` if Close is red, or Run has been red two consecutive weekly evals.

Reaching mandate stage `offer` flips the relevant milestone toward `done`. Five milestones
are seeded against the 2027-04-05 target.

---

## Connection runbook (how Claude Code reaches Artemide here)

**Topology.** Artemide runs in Docker on this host (`/root/artemide`), behind a
Cloudflare Tunnel + Cloudflare Access. The public URL (`artemide.francescofederico.net`)
is **fully CF-Access-gated on every path including `/mcp/`**, so a bearer token alone
can't reach it from a machine client. Instead, the container publishes its port to the
**host loopback only**:

- `docker-compose.yml` → `artemide` service → `ports: ["127.0.0.1:47600:8000"]`
  (loopback-only; not publicly reachable — external ingress still goes via the tunnel).
- Claude Code MCP server (user scope): `http://127.0.0.1:47600/mcp/` (trailing slash
  matters), header `Authorization: Bearer <owner token from /root/artemide/.env
  ARTEMIDE_API_TOKEN>`. Actor `FF`, role `owner`.

**Health / status checks:**
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:47600/health   # expect 200
claude mcp get artemide                                                   # expect ✔ Connected
```

**Re-add / change the server:**
```bash
claude mcp remove artemide -s user
claude mcp add --transport http --scope user artemide http://127.0.0.1:47600/mcp/ \
  --header "Authorization: Bearer $(grep ^ARTEMIDE_API_TOKEN /root/artemide/.env | cut -d= -f2)"
```

**Revert to tunnel-only:** delete the `ports:` block from `docker-compose.yml`, then
`cd /root/artemide && docker compose up -d artemide`. (Claude Code then loses access
until you wire the CF Access service-token route instead.)

**If the tools disappear:** the container was likely recreated. The loopback port is
declared in compose, so it persists across `docker compose up`/restarts — just confirm
`/health` and `claude mcp get artemide`. If the **owner token was rotated** (UI →
Settings → Rotate, which moves the source from `.env` to `system_config`), update the
header with the new value via the re-add commands above.

**Token handling:** the bearer lives in `/root/.claude.json` (user config, this host
only). Don't print it in chat or commit it. Rotating the token requires updating both
Artemide and the MCP header.
