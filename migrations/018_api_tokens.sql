-- v1.2: api_tokens — the owner/bot multi-actor model (Rule 18).
-- Only the SHA-256 hash of a bearer token is stored, never the token itself.
--
-- Backfill note: the existing active token is registered as actor 'FF' role
-- 'owner' by a Python bootstrap (auth.ensure_seed_tokens, run on app startup),
-- because stock SQLite cannot compute SHA-256 inside a migration. This
-- migration is schema-only.

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'bot')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_active ON api_tokens(active);
