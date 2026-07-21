-- Dashboard release: owner feedback on generated Today / next-best-action items.
-- Recommendations themselves are derived from source records on every read. Only
-- owner overrides are persisted, keyed by a stable workstream-qualified source key.

CREATE TABLE IF NOT EXISTS today_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL UNIQUE,
    workstream TEXT NOT NULL CHECK (workstream IN ('executive', 'board')),
    disposition TEXT NOT NULL CHECK (disposition IN ('completed', 'snoozed', 'dismissed')),
    snoozed_until DATE,
    reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (disposition = 'snoozed' AND snoozed_until IS NOT NULL)
        OR (disposition <> 'snoozed' AND snoozed_until IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_today_feedback_disposition
    ON today_feedback(disposition, snoozed_until);
CREATE INDEX IF NOT EXISTS idx_today_feedback_workstream
    ON today_feedback(workstream);

CREATE TRIGGER IF NOT EXISTS trg_today_feedback_updated_at
AFTER UPDATE ON today_feedback
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE today_feedback SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
