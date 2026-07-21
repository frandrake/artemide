-- Neutral public-professional identity and approval-staged AI intake.
-- Identity carries no relationship/workstream state. Cross-domain links are
-- explicit join rows. Executive and board previews are physically separate.

CREATE TABLE IF NOT EXISTS person_identity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    preferred_name TEXT,
    email TEXT,
    linkedin_url TEXT,
    current_title TEXT,
    current_organisation TEXT,
    location TEXT,
    source_url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_person_identity_display_name
    ON person_identity(display_name);
CREATE INDEX IF NOT EXISTS idx_person_identity_email
    ON person_identity(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_person_identity_linkedin
    ON person_identity(linkedin_url) WHERE linkedin_url IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_person_identity_updated_at
AFTER UPDATE ON person_identity
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE person_identity SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS executive_person_link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    person_identity_id INTEGER NOT NULL REFERENCES person_identity(id) ON DELETE RESTRICT,
    partner_id INTEGER NOT NULL UNIQUE REFERENCES partners(id) ON DELETE RESTRICT,
    linked_by TEXT NOT NULL,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_identity_id, partner_id)
);
CREATE INDEX IF NOT EXISTS idx_executive_person_link_person
    ON executive_person_link(person_identity_id);

CREATE TABLE IF NOT EXISTS board_person_link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    person_identity_id INTEGER NOT NULL REFERENCES person_identity(id) ON DELETE RESTRICT,
    board_contact_id INTEGER NOT NULL UNIQUE REFERENCES board_contact(id) ON DELETE RESTRICT,
    linked_by TEXT NOT NULL,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_identity_id, board_contact_id)
);
CREATE INDEX IF NOT EXISTS idx_board_person_link_person
    ON board_person_link(person_identity_id);

CREATE TABLE IF NOT EXISTS executive_ai_intake_preview (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    proposed_payload TEXT NOT NULL CHECK (json_valid(proposed_payload)),
    corrected_payload TEXT CHECK (corrected_payload IS NULL OR json_valid(corrected_payload)),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    model TEXT NOT NULL CHECK (length(trim(model)) > 0),
    prompt TEXT NOT NULL CHECK (length(trim(prompt)) > 0),
    input_hash TEXT NOT NULL CHECK (length(input_hash) = 64),
    sources TEXT NOT NULL CHECK (json_valid(sources)),
    provenance TEXT NOT NULL CHECK (json_valid(provenance)),
    created_by TEXT NOT NULL,
    confirmed_by TEXT,
    rejected_by TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    rejected_at TIMESTAMP,
    CHECK (
        (status = 'draft' AND confirmed_at IS NULL AND rejected_at IS NULL
            AND confirmed_by IS NULL AND rejected_by IS NULL)
        OR (status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL
            AND rejected_at IS NULL AND rejected_by IS NULL)
        OR (status = 'rejected' AND rejected_at IS NOT NULL AND rejected_by IS NOT NULL
            AND confirmed_at IS NULL AND confirmed_by IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_executive_ai_intake_preview_status
    ON executive_ai_intake_preview(status, created_at);
CREATE TRIGGER IF NOT EXISTS trg_executive_ai_intake_preview_updated_at
AFTER UPDATE ON executive_ai_intake_preview
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE executive_ai_intake_preview SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS board_ai_intake_preview (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    proposed_payload TEXT NOT NULL CHECK (json_valid(proposed_payload)),
    corrected_payload TEXT CHECK (corrected_payload IS NULL OR json_valid(corrected_payload)),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    model TEXT NOT NULL CHECK (length(trim(model)) > 0),
    prompt TEXT NOT NULL CHECK (length(trim(prompt)) > 0),
    input_hash TEXT NOT NULL CHECK (length(input_hash) = 64),
    sources TEXT NOT NULL CHECK (json_valid(sources)),
    provenance TEXT NOT NULL CHECK (json_valid(provenance)),
    created_by TEXT NOT NULL,
    confirmed_by TEXT,
    rejected_by TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    rejected_at TIMESTAMP,
    CHECK (
        (status = 'draft' AND confirmed_at IS NULL AND rejected_at IS NULL
            AND confirmed_by IS NULL AND rejected_by IS NULL)
        OR (status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL
            AND rejected_at IS NULL AND rejected_by IS NULL)
        OR (status = 'rejected' AND rejected_at IS NOT NULL AND rejected_by IS NOT NULL
            AND confirmed_at IS NULL AND confirmed_by IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_board_ai_intake_preview_status
    ON board_ai_intake_preview(status, created_at);
CREATE TRIGGER IF NOT EXISTS trg_board_ai_intake_preview_updated_at
AFTER UPDATE ON board_ai_intake_preview
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE board_ai_intake_preview SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
