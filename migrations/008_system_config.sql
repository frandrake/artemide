-- Mutable per-deployment config (token, etc.). Auth middleware reads
-- the api_token key when present; falls back to the env var otherwise.

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
