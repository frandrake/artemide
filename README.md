# Artemide

Private MCP- and REST-accessible CRM for executive-search relationship
tracking. Single-user, self-hosted, Docker-deployed, Cloudflare-fronted.

## Prerequisites

- Docker Engine 25+ with `docker compose`
- Node 20+ (for local UI dev only — production build runs inside Docker)
- Python 3.12+ (for local backend dev only)
- Cloudflare account managing your target domain

## Local development

```bash
git clone <repo> artemide
cd artemide
cp .env.example .env             # then set ARTEMIDE_API_TOKEN and ARTEMIDE_COOKIE_SECRET
docker compose up --build        # backend on :8000 (not published in prod; published locally for dev)
```

In a second terminal:

```bash
cd web
npm install
npm run dev                      # Astro on :4321 with Vite proxy → :8000
```

Visit `http://localhost:4321`. The dev proxy forwards `/api/v1`, `/mcp`,
`/login`, `/logout`, and `/health` to the FastAPI container.

For local-only cookie auth set in `.env`:

```
ARTEMIDE_COOKIE_DOMAIN=
ARTEMIDE_COOKIE_SECURE=false
```

## Production deployment

See **[docs/deployment.md](docs/deployment.md)**. The short version:

1. Set up a Cloudflare Tunnel + (optionally) Cloudflare Access.
2. Paste the tunnel token into `.env` and pick fresh secrets.
3. `docker compose up -d --build`.
4. `docker compose exec artemide uv run python scripts/seed_firms.py`.
5. Wire the URL + Bearer token into Claude.ai's MCP server settings.
6. Install the v2 skill (`skill-update/search-ledger-v2/SKILL.md`) in
   Claude.

After deployment, walk the smoke test in **[docs/smoke-test.md](docs/smoke-test.md)**.

## Operations

- **Token rotation:** prefer the UI (Settings → Rotate token); fallback
  is editing `.env` and restarting only the artemide service. Both
  procedures in **[docs/operations.md](docs/operations.md)**.
- **Backups:** `./scripts/backup.sh` (atomic via `sqlite3 .backup`,
  gzipped, 30-day retention). Daily cron at 03:00 UTC.
- **Restore:** `./scripts/restore.sh <backup-file.db.gz>`.

## Troubleshooting

Common failure modes and fixes in **[docs/troubleshooting.md](docs/troubleshooting.md)**.

## Architecture

Three layers + three transports.

- **Repository** (`src/repository/`) — raw `sqlite3` + Pydantic. No
  business logic.
- **Services** (`src/services/`) — all business logic, audit-logged
  mutations, transactions.
- **Transports** — REST (`src/api/`), MCP (`src/mcp/`), and the static
  Astro UI (`web/`). Each is a thin adapter on top of services.

Every mutation writes an `audit_log` row with `(actor, transport,
before, after)`. Every interactive surface (UI, REST, MCP, CLI) shares
the same auth gate (Bearer token or signed session cookie). All ULIDs
in URLs; integer PKs never leave the database.

Conventions in **[CLAUDE.md](CLAUDE.md)**.

## Tests

```bash
uv run pytest                  # 60+ tests, ≥80 % coverage on services + api
```

Tests run in CI and on every `docker compose build`.

## License

Private. Not for redistribution.

