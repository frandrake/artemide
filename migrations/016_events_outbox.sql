-- v1.2: events_outbox — append-only event source n8n consumes (Rule 19).

CREATE TABLE IF NOT EXISTS events_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_ulid TEXT NOT NULL,
    payload TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    delivery_attempts INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_outbox_delivered_at ON events_outbox(delivered_at);
CREATE INDEX IF NOT EXISTS idx_events_outbox_event_type ON events_outbox(event_type);
CREATE INDEX IF NOT EXISTS idx_events_outbox_created_at ON events_outbox(created_at);
