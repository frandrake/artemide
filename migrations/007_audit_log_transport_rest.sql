-- Phase 3 adds the REST transport. Recreate audit_log so the CHECK
-- constraint accepts 'rest'. Existing 'api' rows are preserved.

CREATE TABLE audit_log_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL
        CHECK (action IN ('create', 'update', 'delete', 'restore', 'log_contact', 'import', 'note', 'plan', 'rotate_token')),
    actor TEXT NOT NULL,
    transport TEXT NOT NULL CHECK (transport IN ('mcp', 'rest', 'cli', 'system', 'web', 'api')),
    payload TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO audit_log_new (id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp)
SELECT id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp FROM audit_log;

DROP TABLE audit_log;
ALTER TABLE audit_log_new RENAME TO audit_log;

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor);
