-- v1.3: interviews — a structured record per interview plus a verbatim
-- transcript. Each interview pairs with an append-only engagement_log row of
-- event_type 'interview' (the existing one-line summary path); the link is held
-- in engagement_log_id. The transcript is indexed for search by the service.

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    engagement_id INTEGER NOT NULL REFERENCES engagements(id),
    engagement_log_id INTEGER REFERENCES engagement_log(id),  -- nullable link
    interview_date DATE NOT NULL,
    round TEXT,
    format TEXT
        CHECK (format IN ('onsite', 'video', 'phone', 'other')),
    panel TEXT,
    summary TEXT,
    transcript TEXT,
    transcript_source TEXT
        CHECK (transcript_source IN ('manual', 'uploaded', 'auto')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interviews_engagement
    ON interviews(engagement_id) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_interviews_updated_at
AFTER UPDATE ON interviews
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE interviews SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
