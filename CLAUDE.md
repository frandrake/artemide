# Artemide — Claude Code Conventions

## Project
Private MCP- and REST-accessible CRM for executive search relationship tracking. Single-user. Self-hosted via Docker on VPS, exposed via Cloudflare Tunnel.

It tracks **two separate domains**: the **executive search** (everything below by default) and a **board / NED search** — a parallel, more-confidential, owner-only domain in its own `board_*` tables that never bleeds into the exec views. See **Board / NED domain** below.

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
- Do NOT let the board/NED domain bleed into exec views — it lives in its own `board_*` tables; never join exec queries to them, and keep it out of exec lists/search/dashboard/reminders by default.
- Do NOT call `OutboxService.emit` or `search_repo.upsert_search_row` from any board service — those two negatives are the board confidentiality spine.

## Naming
- Python modules: lowercase, underscored.
- Pydantic models: PascalCase, suffixed `Input`, `Record`, or `Response`.
- API routes: kebab-case paths, ULIDs in URLs (never integer IDs).
- MCP tools: lowercase verb_noun.
- TypeScript types in web/src/lib/types.ts mirror Pydantic names.

## Database
- SQLite file at `/data/artemide.db`, mounted as named volume.
- All schema changes via numbered SQL migrations. Latest is `029_board_domain.sql` (the board tables).
- Migration runner is idempotent.
- ULIDs on every primary entity.
- Soft delete (deleted_at) on select top-level entities (firms, partners, orgs, engagements, comp scenarios, interviews; board firms/contacts/opportunities).
- All mutations logged to audit_log (handled by service layer, not triggers).
- Enums are dual-validated: a Pydantic `str`-enum AND a SQLite `CHECK`. To add a value, update BOTH (and the mirroring TS type).

## Board / NED domain (parallel, owner-only island)
A second, more-confidential domain for the board/NED search, fully separate from the exec search. Added in migration 029. Mirrors the exec patterns one-to-one but never bleeds into exec views — separation is **structural** (own tables), not a filter you must remember.
- **Tables:** `board_firm`, `board_contact`, `board_opportunity` (+ append-only `board_opportunity_log`), `board_conflict_screen` (1:1), `board_evaluation` (1:1), `board_interaction`, `board_task`, `board_competitor`.
- **Layers:** `src/repository/board_*`, `src/services/board_*`, `src/api/routes_board_*` (`/api/v1/board/*`), `src/mcp/tools/board_*` (`mcp__artemide__board_*`), `web/src/{pages,components}/board/`.
- **Owner-only:** every board service method calls `assert_owner` (reads included) — bot tokens get `forbidden_role` across the whole surface (the `CompService` model).
- **No external sync / no shared search:** board services NEVER call `OutboxService.emit` or `search_repo.upsert_search_row` (see DO NOT). Asserted by tests.
- **Rules:** R1 conflict gate is **advisory** — advancing a `board_opportunity` past `conflict_screen` while `conflict_cleared != yes` returns a `warnings` entry but is allowed (does not block); the stage machine itself is forward-only. R2 — any ticked hard disqualifier forces `verdict = pass`. R3 — every stage change logs to `board_opportunity_log` + `audit_log`. R4 — `board_competitor` is the editable S&P-competitor reference list the conflict screen checks. R5 — a `board_contact` older than ~90 days is flagged `verify_before_send` (computed, never stored).
- **Evaluation:** fixed weights 25/25/20/15/10/5 (chair / mandate / governance / time / brand / terms), computed by the pure `compute_board_evaluation` in `board_evaluation_service` (the `fit_service` analogue).
- **Seed:** `board_import_markdown` ingests the tiered firm/contact ledger (idempotent); `board_export` writes per-domain markdown/CSV, kept apart from the exec export.
- **UI:** a header **mode switcher** (Exec ⇄ Board) swaps the entire nav; domain is carried by URL path (`/board/*`), not a cookie (static Astro output). A vermillion "BOARD" pill + spine mark board mode; a quiet Board-search tile on the exec dashboard links in. Skill: `artemide-board` (separate triggers from `artemide-crm`).

## Brand (UI work)
- Per milanese-visual: Slate Blue #4A5E7C primary, Cool White #F8F9FA backgrounds, Charcoal #2B2D30 body text, Vermillion #E63946 accent, Crimson Pro for headings, Inter for body.
- Never use Steel Blue. Never use gradients, drop shadows, 3D effects.
- 8px spacing multiples.
