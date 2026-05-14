# v2 skill smoke test

Six prompts. Run in a fresh Claude conversation with the v2 skill
loaded **and** the Artemide MCP server attached. All six must succeed,
in order. Each step also has a verification check you can perform
yourself in the UI or via a curl probe.

Pick a placeholder name for the test partner — anything obvious, e.g.
`Test Partner Phase 9`. We'll soft-delete that partner at the end (or
leave it; up to you).

## 1. Audit the ledger

Prompt:

> Show me my ledger state.

Expected: Claude calls `audit_ledger`. Response includes 11 firms, with
TML Partners surfaced as the warm specialist tie. Primary tier
coverage block shows 5 firms; at least some flagged with "no contactable
partner" on a fresh seed.

Verify: `https://artemide.francescofederico.net/audit` shows the same
shape.

## 2. Upsert a partner

Prompt:

> Add a partner at TML Partners: Test Partner Phase 9, practice CMO,
> seniority Partner, based in London.

Expected: Claude calls `upsert_partner` with `firm_ulid` resolved to
TML Partners, `name="Test Partner Phase 9"`, plus the fields. Echo
includes the new partner's ULID.

Verify: open `/firms/<TML ulid>` in the UI — the new partner appears
in the partners grid.

## 3. Log a coffee

Prompt:

> Log a coffee meeting with Test Partner Phase 9 yesterday. I shared
> my Q1 PoV; they introduced me to a peer.

Expected: Claude calls `log_contact` with `channel="coffee"`,
`initiated_by="me"`, `value_given="…Q1 PoV…"`,
`value_received="…intro to peer…"`, and `advance_state=true`. Echo
confirms the partner advanced cold → warming.

Verify: `/partners/<test ulid>` shows the contact in the timeline;
state pill is `warming`; `/audit/log` shows a fresh `log_contact` row
with `transport=mcp`.

## 4. List due touches

Prompt:

> What's due in the next 30 days?

Expected: Claude calls `list_due_touches(window_days=30)`. Response
lists any partners flagged as overdue or due-soon. On a freshly seeded
DB this is typically only the brand-new test partner (if they have a
`next_touch_date` set) and any seeded partners that have ageing
last-contact dates.

## 5. Set quarter topic

Prompt:

> Set Q1 value topic to "Year-ahead PoV on B2B information services
> marketing."

Expected: Claude calls `set_quarter_topic(year=2026, quarter=1,
topic="Year-ahead PoV on B2B information services marketing.")`. Echo
confirms.

Verify: `/plan` shows the updated topic on the Q1 card.

## 6. Plan the quarter

Prompt:

> Plan Q1.

Expected: Claude calls `plan_quarter(year=2026, quarter=1)`. Response
includes the topic from step 5, a list of suggested partner slots
spaced across Q1, and the gaps list (firms with no contactable
partner).

Verify: `/plan` with Q1 expanded matches what Claude described.

## Pass / fail

| Step | Pass criterion |
|---|---|
| 1 | `audit_ledger` returned all expected sections |
| 2 | Partner exists in UI with correct firm linkage |
| 3 | Contact appears in timeline; state advanced |
| 4 | `list_due_touches` returned without error |
| 5 | Q1 topic visible in UI on `/plan` |
| 6 | `plan_quarter` returned slots and topic together |

Any step that surfaces an error message verbatim — surface it back to
the human running the test, don't paper over it.

## Cleanup (optional)

If you don't want the test partner cluttering the directory:

```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  "https://artemide.francescofederico.net/api/v1/partners/<test ulid>"
```

That soft-deletes the partner; the contact log entry stays for audit
integrity.
