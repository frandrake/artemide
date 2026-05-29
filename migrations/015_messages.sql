-- v1.2: messages — the outbound draft queue; the human approval gate.

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    kind TEXT
        CHECK (kind IN ('inbound_reply', 'cadence_touch', 'cold_outreach', 'thank_you', 'custom')),
    partner_id INTEGER REFERENCES partners(id),
    engagement_id INTEGER REFERENCES engagements(id),
    channel TEXT
        CHECK (channel IN ('email', 'inmail', 'message')),
    recipient_hint TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'edited', 'sent', 'discarded')),
    source_ref TEXT,
    created_by_transport TEXT
        CHECK (created_by_transport IN ('mcp', 'rest', 'system')),
    approved_at TIMESTAMP,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_partner_id ON messages(partner_id);
CREATE INDEX IF NOT EXISTS idx_messages_engagement_id ON messages(engagement_id);
-- Inbound idempotency (Rule 20): a source_ref may appear at most once.
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_source_ref
    ON messages(source_ref) WHERE source_ref IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_messages_updated_at
AFTER UPDATE ON messages
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE messages SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
