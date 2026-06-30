-- Board / NED search domain — a parallel, owner-only, unsynced island.
--
-- Fully separated from the executive-search tables: board rows never live in
-- firms/partners/organisations/engagements, so no exec list, search, dashboard,
-- audit report or outbox event can surface them. Eight entities + an append-only
-- opportunity log. Soft-delete on the three top-level entities (firm, contact,
-- opportunity); plain RESTRICT foreign keys (the top-level rows soft-delete, so
-- CASCADE would never fire and RESTRICT prevents orphaning).

-- ---------- board_firm (search practice / platform / network) ----------
CREATE TABLE IF NOT EXISTS board_firm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    firm_type TEXT
        CHECK (firm_type IN ('big_five_board_practice', 'boutique', 'platform', 'network', 'italian_european')),
    geography TEXT,  -- JSON array of UK|Europe|Italy (validated in Pydantic)
    sectors_level TEXT,
    ai_on_boards_hook TEXT,
    tier INTEGER CHECK (tier BETWEEN 1 AND 4),
    status TEXT NOT NULL DEFAULT 'to_approach'
        CHECK (status IN ('to_approach', 'to_register', 'to_join', 'queued', 'contacted',
                          'in_dialogue', 'dormant', 'drafted', 'consider', 'monitor')),
    next_action TEXT,
    notes TEXT,
    source_url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_firm_status
    ON board_firm(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_firm_tier
    ON board_firm(tier) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_board_firm_updated_at
AFTER UPDATE ON board_firm
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_firm SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_contact (partner, chair, connector) ----------
CREATE TABLE IF NOT EXISTS board_contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role_title TEXT,
    firm_id INTEGER REFERENCES board_firm(id),  -- nullable: independent chairs
    practice TEXT
        CHECK (practice IN ('board', 'executive', 'mixed')),
    email TEXT,
    linkedin TEXT,
    mutual_connections TEXT,
    relationship TEXT NOT NULL DEFAULT 'cold'
        CHECK (relationship IN ('cold', 'warm', 'active')),
    last_contact_date DATE,
    source_url TEXT,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_contact_firm_id
    ON board_contact(firm_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_contact_relationship
    ON board_contact(relationship) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_board_contact_updated_at
AFTER UPDATE ON board_contact
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_contact SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_opportunity (a specific board/seat) ----------
CREATE TABLE IF NOT EXISTS board_opportunity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    organisation TEXT NOT NULL,
    board_type TEXT
        CHECK (board_type IN ('listed_ftse350', 'listed_aim', 'pe_vc', 'private', 'mutual', 'charity_arts', 'public_appointment')),
    role TEXT
        CHECK (role IN ('ned', 'sid', 'committee', 'trustee', 'adviser')),
    source_firm_id INTEGER REFERENCES board_firm(id),  -- nullable
    source_text TEXT,                                  -- free-text source alternative
    chair_contact_id INTEGER REFERENCES board_contact(id),  -- nullable
    date_surfaced DATE,
    stage TEXT NOT NULL DEFAULT 'surfaced'
        CHECK (stage IN ('surfaced', 'conflict_screen', 'chair_meeting', 'formal_process', 'final_nomco', 'offer', 'decision')),
    conflict_cleared TEXT NOT NULL DEFAULT 'pending'
        CHECK (conflict_cleared IN ('yes', 'no', 'pending')),
    interest TEXT NOT NULL DEFAULT 'exploratory'
        CHECK (interest IN ('pass', 'exploratory', 'active', 'preferred')),
    next_step TEXT,
    notes TEXT,
    eval_weighted_total REAL,  -- denormalised rollup of board_evaluation
    eval_verdict TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_opportunity_stage
    ON board_opportunity(stage) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_opportunity_interest
    ON board_opportunity(interest) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_opportunity_conflict_cleared
    ON board_opportunity(conflict_cleared) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_opportunity_date_surfaced
    ON board_opportunity(date_surfaced) WHERE deleted_at IS NULL;

CREATE TRIGGER IF NOT EXISTS trg_board_opportunity_updated_at
AFTER UPDATE ON board_opportunity
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_opportunity SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_opportunity_log (append-only stage/event trail, R3) ----------
CREATE TABLE IF NOT EXISTS board_opportunity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    opportunity_id INTEGER NOT NULL REFERENCES board_opportunity(id),
    event_date DATE NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('stage_change', 'conflict_screen', 'evaluation', 'interaction', 'note')),
    from_stage TEXT,
    to_stage TEXT,
    summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_opportunity_log_opportunity_id ON board_opportunity_log(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_board_opportunity_log_event_date ON board_opportunity_log(event_date);

-- ---------- board_conflict_screen (1:1 with opportunity, the gate) ----------
CREATE TABLE IF NOT EXISTS board_conflict_screen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    opportunity_id INTEGER NOT NULL UNIQUE REFERENCES board_opportunity(id),
    is_sp_competitor INTEGER NOT NULL DEFAULT 0,
    result TEXT NOT NULL DEFAULT 'pending'
        CHECK (result IN ('pass', 'fail', 'pending')),
    checked_date DATE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS trg_board_conflict_screen_updated_at
AFTER UPDATE ON board_conflict_screen
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_conflict_screen SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_evaluation (1:1 with opportunity, weighted offer framework) ----------
CREATE TABLE IF NOT EXISTS board_evaluation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    opportunity_id INTEGER NOT NULL UNIQUE REFERENCES board_opportunity(id),
    score_chair_board_quality INTEGER CHECK (score_chair_board_quality BETWEEN 1 AND 5),
    score_mandate_contribution_fit INTEGER CHECK (score_mandate_contribution_fit BETWEEN 1 AND 5),
    score_governance_health_risk INTEGER CHECK (score_governance_health_risk BETWEEN 1 AND 5),
    score_time_conflict_cost INTEGER CHECK (score_time_conflict_cost BETWEEN 1 AND 5),
    score_brand_portfolio_value INTEGER CHECK (score_brand_portfolio_value BETWEEN 1 AND 5),
    score_terms INTEGER CHECK (score_terms BETWEEN 1 AND 5),
    weighted_total REAL,
    hard_disqualifiers TEXT,  -- JSON array of ticked disqualifier keys
    firo_b_fit_notes TEXT,
    verdict TEXT
        CHECK (verdict IN ('proceed', 'proceed_with_caution', 'pass')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS trg_board_evaluation_updated_at
AFTER UPDATE ON board_evaluation
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_evaluation SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_interaction (activity log, polymorphic link) ----------
CREATE TABLE IF NOT EXISTS board_interaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    interaction_date DATE NOT NULL,
    interaction_type TEXT NOT NULL
        CHECK (interaction_type IN ('email', 'call', 'meeting', 'application', 'event', 'note')),
    linked_entity_type TEXT NOT NULL
        CHECK (linked_entity_type IN ('board_firm', 'board_contact', 'board_opportunity')),
    linked_entity_ulid TEXT NOT NULL,
    summary TEXT,
    next_action TEXT,
    due_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_interaction_linked
    ON board_interaction(linked_entity_type, linked_entity_ulid);
CREATE INDEX IF NOT EXISTS idx_board_interaction_due_date ON board_interaction(due_date);

-- ---------- board_task (reminders / follow-ups) ----------
CREATE TABLE IF NOT EXISTS board_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    linked_entity_type TEXT
        CHECK (linked_entity_type IS NULL OR linked_entity_type IN ('board_firm', 'board_contact', 'board_opportunity')),
    linked_entity_ulid TEXT,
    title TEXT NOT NULL,
    due_date DATE,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'done')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_board_task_status_due ON board_task(status, due_date);

CREATE TRIGGER IF NOT EXISTS trg_board_task_updated_at
AFTER UPDATE ON board_task
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_task SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- ---------- board_competitor (R4 S&P competitor exclusion reference list) ----------
CREATE TABLE IF NOT EXISTS board_competitor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS trg_board_competitor_updated_at
AFTER UPDATE ON board_competitor
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_competitor SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
