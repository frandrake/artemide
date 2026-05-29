-- v1.2: organisations — programme system-of-record for what is in motion.

CREATE TABLE IF NOT EXISTS organisations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    sector TEXT,
    scale_band TEXT
        CHECK (scale_band IN ('fortune_500', 'global_equivalent', 'pe_backed', 'other')),
    hq_region TEXT,
    pertinence_note TEXT,
    watch_state TEXT NOT NULL DEFAULT 'watch'
        CHECK (watch_state IN ('watch', 'target', 'active', 'parked', 'excluded')),
    source TEXT,
    external_refs TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_organisations_name_active
    ON organisations(name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_organisations_watch_state ON organisations(watch_state);
CREATE INDEX IF NOT EXISTS idx_organisations_scale_band ON organisations(scale_band);
CREATE INDEX IF NOT EXISTS idx_organisations_deleted_at ON organisations(deleted_at);

CREATE TRIGGER IF NOT EXISTS trg_organisations_updated_at
AFTER UPDATE ON organisations
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE organisations SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
