-- Compensation scenarios — baseline package vs alternatives, GBP only.
-- Seed data (the baseline row) is written by scripts/seed_comp_baseline.py
-- (v1.1 convention: migrations are schema-only, scripts seed).

CREATE TABLE IF NOT EXISTS compensation_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offer'
        CHECK (status IN ('current', 'offer', 'negotiating', 'accepted', 'rejected')),
    is_baseline INTEGER NOT NULL DEFAULT 0,
    engagement_id INTEGER REFERENCES engagements(id),
    base_gbp INTEGER,
    cash_bonus_gbp INTEGER,
    equity_gbp INTEGER,
    equity_note TEXT,
    pension_pct REAL,
    healthcare_gbp INTEGER,
    car_allowance_gbp INTEGER,
    other_gbp INTEGER,
    benefits_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- Exactly one live baseline at any time (comparison anchor).
CREATE UNIQUE INDEX IF NOT EXISTS idx_comp_scenarios_baseline
    ON compensation_scenarios(is_baseline) WHERE is_baseline = 1 AND deleted_at IS NULL;
-- Names unique among live rows (upsert matches by name).
CREATE UNIQUE INDEX IF NOT EXISTS idx_comp_scenarios_name
    ON compensation_scenarios(name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_comp_scenarios_engagement
    ON compensation_scenarios(engagement_id) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_comp_scenarios_updated_at
AFTER UPDATE ON compensation_scenarios
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE compensation_scenarios SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
