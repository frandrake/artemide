# Artemide deployment

Single VPS, Docker Compose, Cloudflare Tunnel for ingress. No ports
published to the host. Two containers: `artemide` (FastAPI + Astro
static dist) and `cloudflared` (the tunnel).

## 1. Host prerequisites

- Docker Engine 25+ with `docker compose` plugin.
- A Cloudflare account with the target domain (e.g.
  `francescofederico.net`) on it.
- DNS for that domain managed by Cloudflare (so the tunnel can attach
  a CNAME automatically).

## 2. Cloudflare Tunnel

1. Cloudflare Zero Trust → **Networks → Tunnels → Create tunnel**.
2. Connector type: **Cloudflared**. Name: `artemide`.
3. Save the tunnel token (long base64 string) — you'll paste it into
   `.env` in a moment. The token is the only credential `cloudflared`
   needs; no certs to mount.
4. Public hostname:
   - **Subdomain:** `artemide`
   - **Domain:** `francescofederico.net`
   - **Service:** `http://artemide:8000`
     (`artemide` is the in-network container hostname; Cloudflare's
     connector reaches it over the compose `internal` network.)
5. Save. Cloudflare creates the DNS CNAME automatically.

## 3. Cloudflare Access (recommended)

Adds an email-verified gate **in front** of the Bearer token so a stolen
token alone can't authenticate.

1. Cloudflare Zero Trust → **Access → Applications → Add application**.
2. Type: **Self-hosted**. Domain: `artemide.francescofederico.net`.
3. Policy: **Allow** when `Emails` includes `francesco@francescofederico.net`.
4. Session duration: 24 hours is reasonable for a personal CRM.

Note: when Access is on, the **MCP transport** needs a Cloudflare Access
**service token** alongside the Bearer header (same pattern as
SearXNG / Crawl4AI in this VPS). Add the Access service-token headers
to the Claude.ai MCP server config in addition to the Bearer token.

## 4. Clone + configure

```bash
git clone <repo> /opt/artemide
cd /opt/artemide
cp .env.example .env
```

Edit `.env`:

| key | value |
|---|---|
| `ARTEMIDE_API_TOKEN` | `openssl rand -hex 32` |
| `TUNNEL_TOKEN` | paste from Cloudflare |
| `ARTEMIDE_DB_PATH` | `/data/artemide.db` (default — fine) |
| `ARTEMIDE_BIND_HOST` | `0.0.0.0` |
| `ARTEMIDE_BIND_PORT` | `8000` |
| `ARTEMIDE_LOG_LEVEL` | `INFO` |
| `ARTEMIDE_ENABLE_DOCS` | `false` in prod |
| `ARTEMIDE_COOKIE_SECRET` | `openssl rand -hex 32` (distinct from API token) |
| `ARTEMIDE_COOKIE_DOMAIN` | `artemide.francescofederico.net` |
| `ARTEMIDE_COOKIE_SECURE` | `true` |

## 5. First build + start

```bash
docker compose up -d --build
docker compose logs -f artemide   # watch startup, ctrl-c when ready
```

`init_db()` runs on startup and applies any pending migrations against
the named `artemide-data` volume.

## 6. Seed

```bash
docker compose exec artemide uv run python scripts/seed_firms.py
```

Output: `11 firm(s) seeded, 0 already existed. 4 quarter topic(s) updated, 0 unchanged.`

(See `docs/smoke-test.md` for the post-seed UI walk-through.)

## 7. Verify

```bash
# Public probe — should 200, no auth required for /health.
curl https://artemide.francescofederico.net/health

# Authenticated probe.
curl -H "Authorization: Bearer $TOKEN" https://artemide.francescofederico.net/api/v1/firms
```

If the tunnel is healthy the Access page (if configured) prompts for
email auth on the second request; after that the Bearer token must
match.

## 8. Wire up Claude

In `claude.ai` → settings → connectors → MCP servers, add:

- URL: `https://artemide.francescofederico.net/mcp/`
- Headers:
  - `Authorization: Bearer <ARTEMIDE_API_TOKEN>`
  - `CF-Access-Client-Id: <service-token-id>` and
    `CF-Access-Client-Secret: <service-token-secret>` if Access is on

Install the v2 skill (`skill-update/search-ledger-v2/SKILL.md`) into the
Claude.ai user skill library.

Run the six-step smoke test from `skill-update/SMOKE_TEST.md`.

## 9. Backup cron

Once everything is green, add the daily backup cron on the host:

```cron
0 3 * * *  cd /opt/artemide && ./scripts/backup.sh >> /var/log/artemide-backup.log 2>&1
```

That's it. The system runs unattended from here. Day-2 tasks live in
`docs/operations.md`; common failure modes live in
`docs/troubleshooting.md`.
