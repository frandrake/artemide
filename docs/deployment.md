# Artemide deployment

Single VPS, Docker Compose, ingress via the host's shared Traefik instance
(not a per-app tunnel). One container: `artemide` (FastAPI + Astro static
dist), published to `127.0.0.1:47600` only. Traefik terminates TLS and
Cloudflare Access gates the hostname in front of that.

## 1. Host prerequisites

- Docker Engine 25+ with the `docker compose` plugin.
- The shared Traefik instance already running and owning 80/443
  (`/docker/traefik`), with the `cloudflare` DNS-01 cert resolver and the
  `cloudflare-only@file` middleware already defined.
- DNS for the target domain (e.g. `francescofederico.net`) managed by
  Cloudflare.

## 2. Traefik route

Add `/docker/traefik/dynamic/artemide.yml`:

```yaml
http:
  routers:
    artemide:
      rule: "Host(`artemide.francescofederico.net`)"
      entryPoints:
        - websecure
      service: artemide
      middlewares:
        - cloudflare-only@file
      tls:
        certResolver: cloudflare
  services:
    artemide:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:47600"
        passHostHeader: true
```

Traefik's file provider watches this directory (`--providers.file.watch=true`)
so no restart is needed.

## 3. DNS + Cloudflare Access

1. Create a proxied (orange-clouded) `A` record: `artemide` → the VPS's
   public IP.
2. Cloudflare Zero Trust → **Access → Applications → Add application**,
   type **Self-hosted**, domain `artemide.francescofederico.net`.
3. Policy: **Allow** when `Emails` includes `francesco@francescofederico.net`
   (mirrors the other self-hosted apps on this VPS — see the "Benny"
   application for the exact template).
4. `cloudflare-only@file` on the Traefik router blocks any direct hit to
   the origin IP that bypasses Access.

Note: the **MCP transport** does *not* go through Cloudflare Access in this
deployment — Hermes reaches it over the host's loopback interface directly
(`http://127.0.0.1:47600/mcp/`, host networking, Bearer token only), never
through the public hostname. Only browser/UI traffic goes through Access.

## 4. Clone + configure

```bash
git clone https://github.com/frandrake/artemide.git /docker/artemide
cd /docker/artemide
cp .env.example .env
```

Edit `.env` (drop `TUNNEL_TOKEN` — no longer used):

| key | value |
|---|---|
| `ARTEMIDE_API_TOKEN` | `openssl rand -hex 32` |
| `ARTEMIDE_DB_PATH` | `/data/artemide.db` (default — fine) |
| `ARTEMIDE_BIND_HOST` | `0.0.0.0` |
| `ARTEMIDE_BIND_PORT` | `8000` |
| `ARTEMIDE_LOG_LEVEL` | `INFO` |
| `ARTEMIDE_ENABLE_DOCS` | `false` in prod |
| `ARTEMIDE_COOKIE_SECRET` | `openssl rand -hex 32` (distinct from API token) |
| `ARTEMIDE_COOKIE_DOMAIN` | `artemide.francescofederico.net` |
| `ARTEMIDE_COOKIE_SECURE` | `true` |
| `ARTEMIDE_N8N_TOKEN` | `openssl rand -hex 32` (bot-role, n8n only) |

## 5. First build + start

```bash
docker compose up -d --build
docker compose logs -f artemide   # watch startup, ctrl-c when ready
```

`init_db()` runs on every startup and applies any pending migrations
against the named `artemide-data` volume, idempotently — safe to restore
an existing `artemide.db` into that volume before first boot instead of
starting empty.

## 6. Seed (fresh installs only — skip if data was restored)

```bash
docker compose exec artemide uv run python scripts/seed_firms.py
```

(See `docs/smoke-test.md` for the post-seed UI walk-through.)

## 7. Verify

```bash
curl https://artemide.francescofederico.net/health   # 200, no auth
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:47600/api/v1/firms
```

An unauthenticated browser hit to the public hostname should 302 to
`https://<team>.cloudflareaccess.com/...`. A direct hit to the origin IP
with the right `Host` header should 403 (blocked by `cloudflare-only`).

## 8. Wire up Hermes (loopback MCP, read-write)

Hermes' `artemide` profile connects directly over the host loopback
interface (its containers run with `network_mode: host`), bypassing
Cloudflare Access entirely — same trust level as a local process. In
`/opt/data/profiles/artemide/config.yaml`:

```yaml
mcp_servers:
  artemide:
    url: http://127.0.0.1:47600/mcp/
    connect_timeout: 15.0
    enabled: true
    headers:
      Authorization: "Bearer ${MCP_ARTEMIDE_API_KEY}"
```

`MCP_ARTEMIDE_API_KEY` goes in `/opt/data/profiles/artemide/.env`. Use the
**owner** token (`ARTEMIDE_API_TOKEN`), not a bot token — the board/NED
domain is owner-only (`assert_owner` on every board method), and this
persona's job spans both exec-search and board search. Restart the
`gateway-artemide` slot (runs inside the **`hermes-gateway`** container,
not `hermes` — the dashboard container explicitly skips gateway
reconciliation) after any config change:

```bash
docker exec hermes-gateway hermes -p artemide gateway stop
docker exec hermes-gateway hermes -p artemide gateway start
```

## 9. Auto-deploy on push

`/docker/artemide-deploy-webhook` is a small FastAPI service that verifies
GitHub's `X-Hub-Signature-256` HMAC and, on push to `master`, runs
`git reset --hard origin/master` + `docker compose up -d --build` against
this exact checkout (bind-mounted, plus the host's Docker socket + CLI so
it drives the host's Docker engine directly — a real, deliberate
host-level privilege grant, confirmed with Francesco before wiring it up).

Fronted by Traefik at `artemide-deploy.francescofederico.net` — proxied,
`cloudflare-only@file` attached, but **no Cloudflare Access application**
(GitHub can't do an interactive Access login; the HMAC secret is the only
gate here). Webhook registered on the repo via `gh api
repos/frandrake/artemide/hooks` with `events: ["push"]`.

Because this clone is the live deploy target, **never leave uncommitted
changes here** — anything not pushed to `master` gets silently discarded
by the next `git reset --hard` on the next push.

## 10. Backup cron

```cron
0 3 * * *  cd /docker/artemide && ./scripts/backup.sh >> /var/log/artemide-backup.log 2>&1
```

Day-2 tasks live in `docs/operations.md`; common failure modes live in
`docs/troubleshooting.md`.

<!-- squash-merge auto-deploy test -->
