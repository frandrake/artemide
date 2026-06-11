-- v1.3: extend audit_log.action CHECK to accept the new actions
-- (attach, interview). SQLite cannot ALTER a CHECK, so rebuild — audit_log is a
-- leaf table (referenced by no FK), safe within the runner's transaction.

DROP TABLE IF EXISTS audit_log_rebuild;

CREATE TABLE audit_log_rebuild (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN
        ('create', 'update', 'delete', 'restore', 'log_contact', 'import', 'note', 'plan',
         'rotate_token', 'draft', 'send', 'template', 'stage',
         'approve', 'ack', 'denied',
         'attach', 'interview')),
    actor TEXT NOT NULL,
    transport TEXT NOT NULL CHECK (transport IN ('mcp', 'rest', 'cli', 'system', 'web', 'api')),
    payload TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO audit_log_rebuild (id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp)
    SELECT id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp FROM audit_log;

DROP TABLE audit_log;
ALTER TABLE audit_log_rebuild RENAME TO audit_log;

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor);
