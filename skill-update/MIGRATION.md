# v1 → v2 migration

The v1 skill assumed Claude saw a markdown ledger Francesco pasted into
each conversation. v2 replaces that with live MCP calls against
Artemide. The data shape is unchanged; the **operating loop** is the
diff.

## Prerequisites

- Artemide is deployed (see `docs/deployment.md`) and reachable at
  `https://artemide.francescofederico.net`.
- `scripts/seed_firms.py` has run — the eleven firms exist.
- You have a valid `ARTEMIDE_API_TOKEN` (and a Cloudflare Access
  service-token pair if Access is enabled).

## Steps

1. **Locate the v1 markdown ledger.** If there is one, save the file
   somewhere stable — call it `ledger-v1-YYYY-MM-DD.md`.

2. **Connect Claude to Artemide.**
   In Claude.ai → settings → connectors → MCP servers:
   - URL: `https://artemide.francescofederico.net/mcp/`
   - Headers:
     - `Authorization: Bearer <ARTEMIDE_API_TOKEN>`
     - `CF-Access-Client-Id: <id>` and `CF-Access-Client-Secret:
       <secret>` if Access is on.
   Confirm with a one-shot `tools/list` from Claude's MCP test panel —
   should return 8 tools.

3. **Import the v1 ledger.** Open a Claude conversation with the v2
   skill loaded **and** the Artemide MCP server attached. Paste:

   > Import the attached markdown ledger.

   …then paste the contents of `ledger-v1-YYYY-MM-DD.md`. Claude will
   call `import_markdown` with `overwrite_existing=false`. The summary
   it echoes back lists firms / partners / contacts created and
   contacts skipped (already present from seeding).

4. **Verify.** Same conversation:

   > Audit the ledger.

   Claude calls `audit_ledger`. Spot-check: firm count, primary-tier
   coverage, dormant list. Walk through the UI at
   `https://artemide.francescofederico.net/firms` and confirm the
   partner counts match what you expected from the v1 file.

5. **Archive v1.** Move `ledger-v1-YYYY-MM-DD.md` to a non-active
   location (e.g. an "Archive/" folder, or a private Drive). Don't
   delete — it's the rollback artefact.

6. **Install v2 skill in Claude.** Replace the v1 skill in your user
   skill library with the contents of
   `skill-update/search-ledger-v2/SKILL.md`. The v2 skill's
   description preserves v1 trigger phrases, so existing prompts keep
   firing.

7. **Run the smoke test.** Execute `skill-update/SMOKE_TEST.md` end to
   end. All six steps must succeed before you call the migration done.

## Rollback

If v2 turns out to be broken:

1. Re-install the v1 skill from the same skill library (the v1 file is
   still in your library history; Claude.ai keeps prior versions).
2. Disconnect the Artemide MCP server from Claude so it doesn't
   confuse future conversations.
3. Restore `ledger-v1-YYYY-MM-DD.md` from archive into the active
   workflow location.
4. Resume the manual markdown loop.
5. File whatever broke against Artemide as a bug; fix; redeploy; redo
   step 7 of the migration before re-installing v2.

## Data-loss safety

Imports are idempotent — running step 3 twice does not duplicate
contacts; the `(partner, date, channel)` uniqueness constraint blocks
that.

Even if v2 corrupts something live, the previous night's `backup.sh`
snapshot is in `./backups/`. Restore with `scripts/restore.sh
./backups/<filename>.db.gz` and the migration becomes a no-op.

## What changes for Francesco

- No more "paste the ledger" step at the top of conversations.
- The UI at `artemide.francescofederico.net` is the canonical view of
  state; the markdown file is no longer authoritative.
- Mutations are immediate. There is no "pending in this conversation"
  state — once Claude calls `log_contact`, it's logged.
- Audit log captures every mutation, so the
  `https://artemide.francescofederico.net/audit/log` page is the
  history of what Claude (or you) did.
