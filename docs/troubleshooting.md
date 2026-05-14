# Artemide troubleshooting

Most common failure modes, ordered by frequency.

## 401 unauthorized

**Symptom:** every authenticated REST or MCP call returns
`{"error":"unauthorized"}`.

**Likely cause:** token mismatch.

**Fix:**

```bash
# What does the server consider authoritative?
curl -H "Authorization: Bearer $TOKEN" \
  https://artemide.francescofederico.net/api/v1/system/info | jq .token_source
```

- `token_source: "environment"` → `.env` is the source of truth. Make
  sure the Bearer header matches `ARTEMIDE_API_TOKEN`.
- `token_source: "database"` → a previous rotation wrote to
  `system_config.api_token`. The env var is no longer accepted. Either
  rotate again via UI (and capture the new token), or clear the row
  manually (see *Token rotation* in `docs/operations.md`).

The Cloudflare Access service token (if Access is on) is a **separate**
header; missing or wrong service-token headers also produce 401 but
from Cloudflare's edge, not from Artemide.

## Cloudflare returns 502 / 1033

**Symptom:** browser shows a Cloudflare error page, not the Artemide
login form.

**Likely cause:** `cloudflared` can't reach `artemide` over the compose
internal network.

**Fix:**

```bash
docker compose ps                 # both should be 'running'
docker compose logs cloudflared   # look for 'connection refused' or DNS errors
docker compose exec cloudflared sh -c 'wget -qO- http://artemide:8000/health'
```

If the `wget` from inside cloudflared fails: the artemide container is
down or not on the same network. `docker compose up -d` usually fixes
it. If both containers are running but cloudflared still can't reach,
restart cloudflared so it re-resolves the DNS name:
`docker compose restart cloudflared`.

## UI shows blank after login

**Symptom:** `POST /login` returns 204 with a Set-Cookie header, but the
next page request is still anonymous and lands back at `/login`.

**Likely cause:** cookie domain mismatch — the browser refuses to
attach a cookie whose `Domain` attribute doesn't match the hostname
you're on.

**Fix:**

```bash
grep COOKIE_DOMAIN .env
# should be exactly artemide.francescofederico.net (no protocol, no slashes)
```

If you're testing locally with `http://localhost:8000`, set
`ARTEMIDE_COOKIE_DOMAIN=""` and `ARTEMIDE_COOKIE_SECURE=false` in `.env`
or override per-run: `docker compose run -e ARTEMIDE_COOKIE_DOMAIN="" …`

## Database locked

**Symptom:** API call returns 500; logs show
`sqlite3.OperationalError: database is locked`.

**Likely cause:** a long-running ad-hoc query or a stale process
holding the WAL.

**Fix:**

- Backups use `sqlite3 .backup` which doesn't take the write lock, so
  cron shouldn't cause this.
- Check for orphaned python processes:
  `docker compose exec artemide ps -ef`
- Restarting the artemide container clears anything stale:
  `docker compose restart artemide`. WAL replays cleanly on start.

## MCP tool calls timeout

**Symptom:** Claude says "the MCP server didn't respond" or tools take
30s+.

**Triage:**

1. `curl -H "Authorization: Bearer $TOKEN" -H "Accept: application/json, text/event-stream" \`
   `  -X POST https://artemide.francescofederico.net/mcp/ \`
   `  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`
   If this returns the tools list, the server is fine — the issue is in
   the Claude.ai MCP server config.
2. Confirm the Claude header includes both the Bearer token **and**, if
   Access is on, the `CF-Access-Client-Id` / `CF-Access-Client-Secret`.
3. Check `docker compose logs -f artemide` while Claude attempts a
   call. If the request never reaches Artemide, the issue is between
   Claude and Cloudflare; if it reaches but errors, the response
   message tells you which tool / service raised it.

## Migration failed on container start

**Symptom:** `docker compose up` exits with `1`; logs show
`sqlite3.OperationalError: duplicate column` or similar mid-migration.

**Likely cause:** a migration was applied via `executescript` outside
the migration runner (so `schema_migrations` doesn't know about it),
and the runner is now re-running it.

**Fix:**

```bash
docker compose run --rm artemide uv run python -c "
import sqlite3
conn = sqlite3.connect('/data/artemide.db')
for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version'):
    print(r[0])
"
```

If a migration that visibly succeeded is missing from this list, insert
it manually:

```bash
docker compose run --rm artemide uv run python -c "
import sqlite3
conn = sqlite3.connect('/data/artemide.db')
conn.execute(\"INSERT INTO schema_migrations(version) VALUES ('006_partner_follow_ups')\")
conn.commit()
"
```

then restart: `docker compose up -d artemide`.

## Restore left the DB unwritable

After running `scripts/restore.sh`, the file ownership may not match
what uvicorn expects in the container.

```bash
docker compose exec artemide ls -la /data/artemide.db
# should be root:root readable; if not:
docker compose exec artemide chmod 644 /data/artemide.db
docker compose restart artemide
```
