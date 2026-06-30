---
name: artemide-board
description: >-
  Operate the Artemide BOARD / NED search domain end-to-end from Claude Code via
  its MCP tools (mcp__artemide__board_*). This is a distinct, more-confidential
  domain, fully separated from the executive job search and the headhunter logs.
  Use whenever Francesco mentions a board seat or non-executive directorship —
  NED, SID, chair, committee, trustee, adviser; a board search firm/platform/
  network (Nurole, Spencer Stuart Board practice, board boutiques); a conflict-of-
  interest screen or S&P competitor check; the conflict-screen queue; the board
  offer evaluation / weighted six-dimension score / hard disqualifiers / verdict
  (proceed | proceed_with_caution | pass); FTSE350/AIM/PE-VC/charity/public-
  appointment boards; nomco / formal process / chair meeting; or phrases like
  "board pipeline", "surface a board opportunity", "advance the board seat",
  "record the conflict screen", "evaluate the board offer", "compare the board
  opportunities", "board outreach due", "verify before send", "the board ledger".
  ALWAYS call a board tool for state — never answer board relationship, pipeline,
  conflict or evaluation state from memory. Keep the board domain out of any
  executive-search list, search, dashboard or message.
---

# artemide-board

Operate the **board / NED search domain** of Artemide entirely from Claude Code.
All state is read and written through the **`artemide` MCP server**, board tools
exposed as **`mcp__artemide__board_<tool>`**. This domain is **owner-only** (a
bot token gets `forbidden_role`), **never externally synced** (no n8n/outbox),
and **never appears in the executive-search views, global search or dashboard**.

**Separation (hard rule).** The board search is a separate domain from the
executive job search and the headhunter logs. Do not mix the two: a board firm
is a `board_*` record, not an exec firm; a board contact is not an exec partner.
Never let board records, names or activity surface in any executive list,
search, reminder or message. Treat the board domain as the more sensitive one.

**Always call a tool for state.** Never answer board pipeline, conflict or
evaluation state from memory.

## The model (seven entities + a reference list)

- **board firm** — search practice / platform / network. `firm_type`
  (big_five_board_practice | boutique | platform | network | italian_european),
  `geography` (UK | Europe | Italy), `tier` 1–4, `status` (to_approach →
  in_dialogue → dormant), `ai_on_boards_hook`.
- **board contact** — partner, chair or connector. `practice` (board | executive
  | mixed), `relationship` (cold | warm | active). Shows **verify_before_send**
  when `last_contact_date` is older than ~90 days (R5 — people move firms).
- **board opportunity** — a specific seat. `board_type`, `role` (ned | sid |
  committee | trustee | adviser), ordered `stage`: surfaced → conflict_screen →
  chair_meeting → formal_process → final_nomco → offer → decision.
- **conflict screen** (1:1) — `result` (pass | fail | pending) maps to the
  opportunity's `conflict_cleared` (yes | no | pending).
- **evaluation** (1:1) — six 1–5 scores with fixed weights (chair/board quality
  25, mandate/contribution fit 25, governance health/risk 20, time/conflict cost
  15, brand/portfolio 10, terms 5), a computed `weighted_total`, hard
  disqualifiers, and a `verdict`.
- **interaction** / **task** — board-only activity log and reminders.
- **competitor** — the editable S&P competitor reference list (R4).

## The rules (enforced server-side)

- **R1 conflict gate (ADVISORY).** Advancing past `conflict_screen` while
  `conflict_cleared != yes` is *permitted* but returns a `warnings` entry. Record
  a passing conflict screen (`board_record_conflict_screen`) to clear it.
- **R2 disqualifier override.** Any ticked hard disqualifier forces
  `verdict = pass` regardless of score. `board_set_evaluation` returns
  `forced_pass: true` in that case.
- **R3 stage audit.** Every stage change is logged on the opportunity's trail.
- **R5 contact-move flag.** Re-verify a contact's firm before sending if their
  last contact is >90 days old.

## Tools

`board_upsert_firm` · `board_list_firms` · `board_get_firm` ·
`board_upsert_contact` · `board_list_contacts` (stale=true for R5) ·
`board_upsert_opportunity` · `board_list_opportunities` · `board_get_opportunity`
· `board_advance_opportunity` (surfaces the advisory R1 warning) ·
`board_record_conflict_screen` · `board_set_evaluation` (returns weighted_total,
verdict, forced_pass, breakdown) · `board_compare_evaluations` ·
`board_log_interaction` · `board_upsert_task` · `board_list_tasks` · `board_due`
· `board_list_competitors` · `board_upsert_competitor` · `board_import_markdown`
(seed the tiered ledger; idempotent) · `board_export`.

The board UI lives under `https://artemide.francescofederico.net/board`
(toggle to **Board** mode in the header — the nav swaps entirely; a vermillion
"BOARD" indicator marks the confidential domain).
