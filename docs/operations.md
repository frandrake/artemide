# Artemide operations

Day-2 tasks. Assumes the deployment in `docs/deployment.md` is up.

## Daily

```bash
# tail logs
docker compose logs -f artemide

# restart only artemide (cloudflared keeps running)
docker compose up -d --no-deps artemide

# trigger an ad-hoc backup
./scripts/backup.sh
```

## Token rotation

The bearer token sits in two places: the `.env` file and the database
(`system_config.api_token`). The auth middleware prefers the DB value
when present, so rotation works without a process restart.

### Preferred: rotate via UI

1. Sign in to `https://artemide.francescofederico.net`.
2. **Settings → Rotate token** → confirm in the dialog.
3. Copy the new token from the result panel (shown **once**).
4. Update the Claude.ai MCP server **Authorization** header.
5. (Optional) update `.env` on the host so the next rebuild matches the
   live token. The DB value still wins, so this is cosmetic.

The old token starts returning 401 immediately.

### Manual rotation (env-only)

Use this if the UI is down.

```bash
NEW=$(openssl rand -hex 32)
# edit .env: ARTEMIDE_API_TOKEN=$NEW
docker compose up -d --no-deps artemide   # picks up new env
```

If a previous rotation wrote to `system_config`, you also need to clear
that row so the env value takes over:

```bash
docker compose exec artemide uv run python -c "
import sqlite3
conn = sqlite3.connect('/data/artemide.db')
conn.execute('DELETE FROM system_config WHERE key = \"api_token\"')
conn.commit()
"
```

After either path: update the Claude.ai MCP server header. Verify with
a single tool call.

## Cookie secret rotation (every 6 months)

`ARTEMIDE_COOKIE_SECRET` signs the session cookie. Rotating it
invalidates every existing browser session immediately, which is the
point.

```bash
# edit .env: ARTEMIDE_COOKIE_SECRET=$(openssl rand -hex 32)
docker compose up -d --no-deps artemide
```

Then sign back in.

## Backups

- `./scripts/backup.sh` — atomic via `sqlite3 .backup`, gzipped, kept
  for 30 days in `./backups/`.
- Cron: `0 3 * * *` (UTC) per `docs/deployment.md`.
- Off-site (optional): mirror `./backups/` to Cloudflare R2 with
  `rclone` after each cron run:
  ```cron
  5 3 * * *  rclone sync /opt/artemide/backups r2:artemide-backups
  ```

Restore: `./scripts/restore.sh ./backups/backup-YYYYMMDD-HHMMSS.db.gz`.
The script copies the gunzipped file in, mv's it over the live DB, and
restarts the container so SQLite doesn't replay WAL on top.

## Monitoring

Minimum viable: external HTTP check on
`https://artemide.francescofederico.net/health` every 5 minutes
(UptimeRobot, BetterUptime, or Cloudflare Healthchecks). Anything that
isn't `200 {"status":"ok"}` warrants attention.

Internal: `docker compose logs --tail=200 artemide` after any
deployment. Real-time `docker compose logs -f` during incidents.

## Updating the codebase

```bash
cd /opt/artemide
git pull
docker compose build artemide
docker compose up -d --no-deps artemide
docker compose logs -f artemide   # confirm clean start
```

Migrations run automatically on container start. If a migration fails,
the container exits non-zero; logs show which `*.sql` file errored.

## Container hygiene

`docker compose down` does **not** drop the `artemide-data` volume.
`docker compose down -v` does — only run that against a deliberately
disposable dev stack.

## Schedule overview

| When         | Task                                          |
|--------------|-----------------------------------------------|
| daily 03:00  | `scripts/backup.sh` via cron                  |
| weekly       | check `./backups/` size, spot-restore drill   |
| 6-monthly    | rotate `ARTEMIDE_COOKIE_SECRET`               |
| as needed    | rotate `ARTEMIDE_API_TOKEN` via UI            |
| after deploy | run smoke test in `docs/smoke-test.md`        |
