-- v1.2: engagement_profile — versioned fit criteria; exactly one active row.
-- Seed data is written by scripts/seed_engagement_profile.py (v1.1 convention:
-- migrations are schema-only, scripts seed).

CREATE TABLE IF NOT EXISTS engagement_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    version INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 0,
    comp_base_floor_gbp INTEGER NOT NULL,
    comp_total_target_gbp INTEGER NOT NULL,
    accepted_role_types TEXT NOT NULL,
    accepted_scale_bands TEXT NOT NULL,
    hard_exclusions TEXT NOT NULL,
    weights TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Enforces exactly one active profile version.
CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_active
    ON engagement_profile(active) WHERE active = 1;
