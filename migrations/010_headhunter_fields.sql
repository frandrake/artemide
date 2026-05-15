-- Headhunter dataset schema extension.
-- Adds structured intelligence fields to firms and partners,
-- and creates the engagement_calendar table for the 12-month plan.
-- No existing columns are modified or removed.

-- firms: market intelligence columns
ALTER TABLE firms ADD COLUMN market_tier TEXT;           -- 'tier-1-global' | 'specialist-boutique' | 'honourable-mention'
ALTER TABLE firms ADD COLUMN strategic_fit TEXT;         -- 'HIGH' | 'MEDIUM' | 'LOW'
ALTER TABLE firms ADD COLUMN ned_practice_strength TEXT; -- 'HIGH' | 'MEDIUM' | 'LOW' | 'N/A'
ALTER TABLE firms ADD COLUMN hq_address TEXT;
ALTER TABLE firms ADD COLUMN sectors TEXT;               -- comma-separated
ALTER TABLE firms ADD COLUMN cmo_practice_depth TEXT;
ALTER TABLE firms ADD COLUMN comp_transparency TEXT;
ALTER TABLE firms ADD COLUMN candidate_reputation TEXT;
ALTER TABLE firms ADD COLUMN b2b_fs_reputation TEXT;

-- partners: intelligence and relationship columns
-- (linkedin_url, location, introduced_via already exist from migrations 001 and 009)
ALTER TABLE partners ADD COLUMN practice_focus TEXT;
ALTER TABLE partners ADD COLUMN strategic_relevance TEXT; -- 'HIGH' | 'MEDIUM' | 'LOW'
ALTER TABLE partners ADD COLUMN warm_intro_angle TEXT;
ALTER TABLE partners ADD COLUMN thought_leadership TEXT;  -- comma-separated list
ALTER TABLE partners ADD COLUMN prior_career TEXT;
ALTER TABLE partners ADD COLUMN ned_gateway INTEGER NOT NULL DEFAULT 0;

-- Engagement calendar: 12-month outreach plan mapped to tracks.
-- Kept separate from value_calendar (quarterly topic planner) which
-- has an incompatible schema for this purpose.
CREATE TABLE IF NOT EXISTS engagement_calendar (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid        TEXT    NOT NULL UNIQUE,
    firm_id     INTEGER REFERENCES firms(id),
    partner_id  INTEGER REFERENCES partners(id),
    due_date    DATE    NOT NULL,
    title       TEXT    NOT NULL,
    description TEXT,
    status      TEXT    NOT NULL DEFAULT 'not_set'
                CHECK (status IN ('not_set', 'planned', 'in_progress', 'complete')),
    track       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_engagement_cal_due_date ON engagement_calendar(due_date);
CREATE INDEX IF NOT EXISTS idx_engagement_cal_track    ON engagement_calendar(track);
CREATE INDEX IF NOT EXISTS idx_engagement_cal_firm     ON engagement_calendar(firm_id);
CREATE INDEX IF NOT EXISTS idx_engagement_cal_partner  ON engagement_calendar(partner_id);
