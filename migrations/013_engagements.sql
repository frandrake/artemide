-- v1.2: engagements (one row per role-in-motion) + append-only engagement_log.

CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    org_id INTEGER NOT NULL REFERENCES organisations(id),
    role_title TEXT NOT NULL,
    role_type TEXT
        CHECK (role_type IN ('cmo', 'cmgo', 'cco', 'transformation', 'ned', 'other')),
    source TEXT
        CHECK (source IN ('inbound_partner', 'radar', 'referral', 'direct', 'flywheel', 'other')),
    source_partner_id INTEGER REFERENCES partners(id),
    stage TEXT NOT NULL DEFAULT 'surfaced'
        CHECK (stage IN ('surfaced', 'exploratory', 'formal', 'final', 'offer', 'decision', 'closed')),
    interest TEXT NOT NULL DEFAULT 'exploratory'
        CHECK (interest IN ('pass', 'exploratory', 'active', 'preferred')),
    comp_base_gbp INTEGER,
    comp_total_gbp INTEGER,
    comp_equity_note TEXT,
    fit_score INTEGER,
    fit_breakdown TEXT,
    next_step TEXT,
    next_step_date DATE,
    closed_reason TEXT
        CHECK (closed_reason IN ('withdrew', 'rejected', 'declined_offer', 'accepted', 'lapsed')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engagements_org_id
    ON engagements(org_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_engagements_stage
    ON engagements(stage) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_engagements_interest
    ON engagements(interest) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_engagements_next_step_date
    ON engagements(next_step_date) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_engagements_source_partner_id
    ON engagements(source_partner_id) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_engagements_updated_at
AFTER UPDATE ON engagements
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE engagements SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS engagement_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    engagement_id INTEGER NOT NULL REFERENCES engagements(id),
    event_date DATE NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('stage_change', 'interview', 'reference', 'offer', 'note', 'withdrawal')),
    from_stage TEXT,
    to_stage TEXT,
    summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engagement_log_engagement_id ON engagement_log(engagement_id);
CREATE INDEX IF NOT EXISTS idx_engagement_log_event_date ON engagement_log(event_date);
