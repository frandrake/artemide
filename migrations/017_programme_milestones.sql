-- v1.2: programme_milestones — time-boxed milestones along the phase track.
-- Seed rows are written by scripts/seed_milestones.py (schema-only migration).

CREATE TABLE IF NOT EXISTS programme_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    phase TEXT
        CHECK (phase IN ('build', 'seed', 'run', 'close', 'exit')),
    label TEXT NOT NULL,
    target_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'on_track', 'at_risk', 'done')),
    metric_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_programme_milestones_phase ON programme_milestones(phase);
CREATE INDEX IF NOT EXISTS idx_programme_milestones_target_date ON programme_milestones(target_date);

CREATE TRIGGER IF NOT EXISTS trg_programme_milestones_updated_at
AFTER UPDATE ON programme_milestones
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE programme_milestones SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
