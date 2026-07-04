-- 030: board target — the NED-search goal (single row) + outcome on opportunities.
-- Board domain (owner-only island): no outbox events, no shared search rows.

CREATE TABLE IF NOT EXISTS board_target (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    seats_target INTEGER NOT NULL DEFAULT 2 CHECK (seats_target >= 1),
    target_date DATE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Single-row semantics: there is exactly one live target.
CREATE UNIQUE INDEX IF NOT EXISTS idx_board_target_singleton ON board_target((1));

CREATE TRIGGER IF NOT EXISTS trg_board_target_updated_at
AFTER UPDATE ON board_target
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_target SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- How a decided opportunity ended. NULL while in motion.
ALTER TABLE board_opportunity ADD COLUMN outcome TEXT
    CHECK (outcome IN ('accepted', 'declined', 'lost'));
