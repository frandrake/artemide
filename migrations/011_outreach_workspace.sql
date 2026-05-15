-- Phase 11: outreach workspace.
-- Adds outreach_stage to partners (Kanban axis), templates,
-- outreach_draft + outreach_draft_version + outreach_message
-- (drafting → atomic send), and widens audit_log action vocabulary.

-- 1. Kanban axis on partners
ALTER TABLE partners ADD COLUMN outreach_stage TEXT NOT NULL DEFAULT 'researched'
    CHECK (outreach_stage IN ('researched','drafted','sent','replied','met','ongoing','paused','dropped'));
CREATE INDEX IF NOT EXISTS idx_partners_outreach_stage ON partners(outreach_stage);

-- 2. Templates
CREATE TABLE IF NOT EXISTS template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    channel TEXT NOT NULL CHECK (channel IN ('email','linkedin','message','other')),
    subject_template TEXT,
    body_template TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_template_category   ON template(category);
CREATE INDEX IF NOT EXISTS idx_template_deleted_at ON template(deleted_at);

CREATE TRIGGER IF NOT EXISTS trg_template_updated_at
AFTER UPDATE ON template
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE template SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- 3. Outreach drafts (head only; history in outreach_draft_version)
-- sent_message_id is intentionally NOT a declared FK because outreach_message
-- is created later in this file. Application-layer integrity guarantees it.
CREATE TABLE IF NOT EXISTS outreach_draft (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES template(id) ON DELETE SET NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email','linkedin','message','other')),
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','ready','sent','archived')),
    version INTEGER NOT NULL DEFAULT 1,
    sent_message_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_outreach_draft_partner ON outreach_draft(partner_id, status);
CREATE INDEX IF NOT EXISTS idx_outreach_draft_status  ON outreach_draft(status);

CREATE TRIGGER IF NOT EXISTS trg_outreach_draft_updated_at
AFTER UPDATE ON outreach_draft
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE outreach_draft SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- 4. Per-version snapshots
CREATE TABLE IF NOT EXISTS outreach_draft_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    draft_id INTEGER NOT NULL REFERENCES outreach_draft(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    author_actor TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (draft_id, version)
);
CREATE INDEX IF NOT EXISTS idx_outreach_draft_version_draft
    ON outreach_draft_version(draft_id, version DESC);

-- 5. Outreach messages (immutable send log)
CREATE TABLE IF NOT EXISTS outreach_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    draft_id INTEGER NOT NULL REFERENCES outreach_draft(id) ON DELETE RESTRICT,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    contact_log_id INTEGER NOT NULL REFERENCES contact_log(id) ON DELETE RESTRICT,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_via TEXT NOT NULL CHECK (sent_via IN ('email','linkedin','message','other')),
    recipient_handle TEXT,
    subject_snapshot TEXT,
    body_snapshot TEXT NOT NULL,
    version_sent INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outreach_message_partner ON outreach_message(partner_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_message_sent_at ON outreach_message(sent_at);

-- 6. Widen audit_log action vocabulary (same pattern as migration 007). One-time recreate.
CREATE TABLE audit_log_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN
        ('create','update','delete','restore','log_contact','import','note','plan','rotate_token',
         'draft','send','template','stage')),
    actor TEXT NOT NULL,
    transport TEXT NOT NULL CHECK (transport IN ('mcp','rest','cli','system','web','api')),
    payload TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO audit_log_new (id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp)
SELECT id, ulid, entity_type, entity_id, action, actor, transport, payload, timestamp FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_new RENAME TO audit_log;

CREATE INDEX IF NOT EXISTS idx_audit_log_entity    ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor     ON audit_log(actor);
