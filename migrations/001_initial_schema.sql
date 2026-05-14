-- Core entities: firms, partners, contact_log, value_calendar.

CREATE TABLE IF NOT EXISTS firms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL CHECK (tier IN ('primary', 'specialist', 'ned')),
    region TEXT,
    relationship_state TEXT NOT NULL DEFAULT 'cold'
        CHECK (relationship_state IN ('warm', 'warming', 'cold', 'dormant')),
    primary_focus TEXT,
    notes_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_firms_tier ON firms(tier);
CREATE INDEX IF NOT EXISTS idx_firms_relationship_state ON firms(relationship_state);
CREATE INDEX IF NOT EXISTS idx_firms_deleted_at ON firms(deleted_at);

CREATE TRIGGER IF NOT EXISTS trg_firms_updated_at
AFTER UPDATE ON firms
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE firms SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    firm_id INTEGER NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    title TEXT,
    practice TEXT,
    seniority TEXT,
    email TEXT,
    linkedin_url TEXT,
    relationship_state TEXT NOT NULL DEFAULT 'cold'
        CHECK (relationship_state IN ('warm', 'warming', 'cold', 'dormant')),
    last_contact_date DATE,
    next_touch_date DATE,
    next_touch_topic TEXT,
    notes_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE (firm_id, name)
);

CREATE INDEX IF NOT EXISTS idx_partners_firm_id ON partners(firm_id);
CREATE INDEX IF NOT EXISTS idx_partners_relationship_state ON partners(relationship_state);
CREATE INDEX IF NOT EXISTS idx_partners_last_contact_date ON partners(last_contact_date);
CREATE INDEX IF NOT EXISTS idx_partners_next_touch_date ON partners(next_touch_date);
CREATE INDEX IF NOT EXISTS idx_partners_deleted_at ON partners(deleted_at);

CREATE TRIGGER IF NOT EXISTS trg_partners_updated_at
AFTER UPDATE ON partners
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE partners SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS contact_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    contact_date DATE NOT NULL,
    channel TEXT NOT NULL
        CHECK (channel IN ('email', 'call', 'coffee', 'event', 'inmail', 'message', 'other')),
    initiated_by TEXT NOT NULL CHECK (initiated_by IN ('me', 'them')),
    summary TEXT,
    value_given TEXT,
    value_received TEXT,
    follow_up TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact_log_partner_id ON contact_log(partner_id);
CREATE INDEX IF NOT EXISTS idx_contact_log_contact_date ON contact_log(contact_date);
CREATE INDEX IF NOT EXISTS idx_contact_log_channel ON contact_log(channel);
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_log_partner_date_channel
    ON contact_log(partner_id, contact_date, channel);

CREATE TABLE IF NOT EXISTS value_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    topic TEXT,
    status TEXT NOT NULL DEFAULT 'not_set'
        CHECK (status IN ('not_set', 'planned', 'in_progress', 'complete')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (year, quarter)
);

CREATE INDEX IF NOT EXISTS idx_value_calendar_year ON value_calendar(year);
CREATE INDEX IF NOT EXISTS idx_value_calendar_status ON value_calendar(status);

CREATE TRIGGER IF NOT EXISTS trg_value_calendar_updated_at
AFTER UPDATE ON value_calendar
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE value_calendar SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
