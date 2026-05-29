# Artemide v1.2 — n8n workflow layer

n8n holds orchestration; Artemide holds state. These eight workflows mount onto
Artemide's REST API, the bot mailbox, the company-data MCP, and Claude. Claude
classifies and drafts; Artemide scores and persists; **only the Sender sends mail,
and only after the owner approves a message in the Artemide UI.**

## Workflows

| File | Trigger | What it does | Human gate |
|---|---|---|---|
| `01_radar.json` | Schedule, daily 06:00 | Upsert orgs/engagements, rescore, Claude morning digest | Owner reads digest |
| `02_cadence.json` | Schedule, weekly + due dates | `GET /planning/due-touches`, propose cadence drafts | Owner approves in `/messages` |
| `03_inbound_triage.json` | Bot-mailbox watch | Classify + draft reply, propose with `source_ref` | Owner approves |
| `04_dossier.json` | Outbox `engagement.surfaced` | Company-data MCP brief → `POST /notes` | None (read-only) |
| `05_prep_pack.json` | Outbox `engagement.stage_changed`→`formal` | SRA prep pack → `POST /notes` | Owner reviews |
| `06_flywheel.json` | Schedule, weekly | Match signals → orgs/engagements (`source=flywheel`) | Owner decides |
| `07_rollup.json` | Schedule, Friday 16:00 | Friday read-out from `/programme/status` etc. | Owner reviews |
| `sender.json` | Outbox `message.approved` | **The only sender.** Send from bot mailbox → `POST /messages/{ulid}/sent` | — |

The outbox-driven workflows (4, 5, sender) poll `GET /api/v1/events`, filter by
`event_type`, act, then `POST /api/v1/events/{ulid}/ack`. Consumers dedupe on the
event `ulid` (at-least-once delivery, Rule 19).

## Required credentials (never commit values)

1. **Artemide Bot Token** — n8n *Header Auth* credential named `Artemide Bot Token`,
   header `Authorization: Bearer <bot-token>`. Issue the token in Artemide via
   **Settings → Automation** (or `POST /api/v1/admin/issue-bot-token` as owner). It is
   a **bot-role** token: it may read, create orgs/engagements/notes/messages, advance
   stages, and ack events — but **never** approve, delete, set the profile, or rotate
   tokens (Rule 18). The bot token getting a 403 on `/approve` is expected.
2. **Bot mailbox OAuth** — Microsoft 365 / Outlook OAuth2 for the bot inbox
   (workflows 3 and Sender). Used only to read inbound and to send approved mail.
3. **Company-data MCP** — the connected company-research MCP (workflow 4).
4. **Claude API** — Anthropic API key for classification and drafting.

Bind the mailbox/Claude/MCP nodes to your credentials.

**Important — Artemide is reached over the internal docker network.** The HTTP nodes
call **`http://artemide:8000`**, not the public hostname: the n8n and artemide
containers share the `n8n_default` docker network, and the public
`artemide.francescofederico.net` sits behind **Cloudflare Access** (a browser gate
that returns a login page to header-token API calls). The Artemide *Header Auth*
credential's header **name must be `Authorization`**, value `Bearer <bot-token>`.
The Claude node calls `https://api.anthropic.com/v1/messages` with an `x-api-key`
Header Auth credential.

## The send loop (cardinal rule)

```
Cadence/Inbound → POST /messages (proposed)
        owner approves in Artemide /messages UI   ← the only path to 'approved'
        Artemide emits message.approved to the outbox
Sender consumes message.approved → sends from bot mailbox → POST /messages/{ulid}/sent
```

No workflow calls `/messages/{ulid}/approve`; the bot token would be rejected anyway.
Artemide never sends mail itself.

## Import

These JSON files import via the n8n UI (**Workflows → Import from File**) or were
imported programmatically and left **inactive**. Activate only after you have
eyeballed proposed drafts for a week with the Sender still off (per the spec's
roll-out note).

## Idempotency

Every write carries an `Idempotency-Key` header. Inbound proposals carry a
`source_ref` (the mail id) — a second propose on the same ref returns the original
message (Rule 20). All workflows are safe to re-run.

> Credentials themselves are never committed. The n8n credential store is git-ignored.
