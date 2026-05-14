# Artemide — Claude Code Conventions

## Project
Private MCP- and REST-accessible CRM for executive search relationship tracking. Single-user. Self-hosted via Docker on VPS, exposed via Cloudflare Tunnel.

## Stack
- Python 3.12 / FastAPI / FastMCP (mounted as sub-app) / Pydantic 2 / sqlite3 stdlib / ulid-py
- Frontend: Astro 5 / React 19 islands / Tailwind 4 / TypeScript
- uv for Python deps, npm for frontend deps, pytest for tests, Docker for deployment

## Commands
- Install Python deps: `uv sync`
- Install web deps: `cd web && npm install`
- Run tests: `uv run pytest`
- Run web dev: `cd web && npm run dev`
- Run API locally: `uv run python -m src.app`
- Run migrations: `uv run python -m src.db migrate`
- Build container: `docker compose build`
- Run container: `docker compose up`

## Architecture (three layers + three transports)
- `src/repository/` — raw SQL, returns Pydantic models
- `src/services/` — business logic, calls repository, writes audit log
- `src/api/` — REST endpoints, calls services
- `src/mcp/` — MCP tools, calls services
- `web/` — Astro frontend, calls REST

## DO NOT
- Do NOT use any ORM. Raw sqlite3 + Pydantic only.
- Do NOT put business logic in repositories or transports. Only in services.
- Do NOT use async sqlite. Sync DB layer; FastAPI handles concurrency.
- Do NOT commit `data/`, `.env`, `*.db`, `web/node_modules/`, `web/dist/`.
- Do NOT publish any port to host. All ingress via Cloudflare Tunnel.
- Do NOT use names that signal job-search activity in any logs, comments, or output.

## Naming
- Python modules: lowercase, underscored.
- Pydantic models: PascalCase, suffixed `Input`, `Record`, or `Response`.
- API routes: kebab-case paths, ULIDs in URLs (never integer IDs).
- MCP tools: lowercase verb_noun.
- TypeScript types in web/src/lib/types.ts mirror Pydantic names.

## Database
- SQLite file at `/data/artemide.db`, mounted as named volume.
- All schema changes via numbered SQL migrations.
- Migration runner is idempotent.
- ULIDs on every primary entity.
- Soft delete (deleted_at) on firms and partners only.
- All mutations logged to audit_log (handled by service layer, not triggers).

## Brand (UI work)
- Per milanese-visual: Slate Blue #4A5E7C primary, Cool White #F8F9FA backgrounds, Charcoal #2B2D30 body text, Vermillion #E63946 accent, Crimson Pro for headings, Inter for body.
- Never use Steel Blue. Never use gradients, drop shadows, 3D effects.
- 8px spacing multiples.
