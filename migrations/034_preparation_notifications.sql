-- Immutable, provenance-backed preparation packs and redacted notification queue.
-- Executive and board pack persistence is deliberately physically separate.

CREATE TABLE IF NOT EXISTS executive_preparation_pack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    target_entity_type TEXT NOT NULL,
    target_entity_ulid TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'superseded')),
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    generated_by TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    generation_metadata TEXT,
    proposed_by TEXT NOT NULL,
    proposed_at TEXT NOT NULL,
    confirmed_by TEXT,
    confirmed_at TEXT,
    superseded_at TEXT,
    UNIQUE(target_entity_type, target_entity_ulid, version),
    CHECK (
        (status = 'proposed' AND confirmed_by IS NULL AND confirmed_at IS NULL AND superseded_at IS NULL)
        OR (status = 'confirmed' AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND superseded_at IS NULL)
        OR (status = 'superseded' AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND superseded_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS executive_preparation_pack_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    pack_id INTEGER NOT NULL REFERENCES executive_preparation_pack(id),
    source_kind TEXT NOT NULL,
    source_ulid TEXT,
    public_url TEXT,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    retrieved_at TEXT NOT NULL,
    citation_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK ((source_ulid IS NOT NULL) <> (public_url IS NOT NULL)),
    UNIQUE(pack_id, citation_label)
);

CREATE TABLE IF NOT EXISTS board_preparation_pack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    board_opportunity_ulid TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'superseded')),
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    generated_by TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    generation_metadata TEXT,
    proposed_by TEXT NOT NULL,
    proposed_at TEXT NOT NULL,
    confirmed_by TEXT,
    confirmed_at TEXT,
    superseded_at TEXT,
    UNIQUE(board_opportunity_ulid, version),
    CHECK (
        (status = 'proposed' AND confirmed_by IS NULL AND confirmed_at IS NULL AND superseded_at IS NULL)
        OR (status = 'confirmed' AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND superseded_at IS NULL)
        OR (status = 'superseded' AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND superseded_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS board_preparation_pack_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    pack_id INTEGER NOT NULL REFERENCES board_preparation_pack(id),
    source_kind TEXT NOT NULL,
    source_ulid TEXT,
    public_url TEXT,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    retrieved_at TEXT NOT NULL,
    citation_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK ((source_ulid IS NOT NULL) <> (public_url IS NOT NULL)),
    UNIQUE(pack_id, citation_label)
);

CREATE INDEX IF NOT EXISTS idx_exec_prep_target
    ON executive_preparation_pack(target_entity_type, target_entity_ulid, version DESC);
CREATE INDEX IF NOT EXISTS idx_board_prep_target
    ON board_preparation_pack(board_opportunity_ulid, version DESC);
CREATE INDEX IF NOT EXISTS idx_exec_prep_source_pack
    ON executive_preparation_pack_source(pack_id);
CREATE INDEX IF NOT EXISTS idx_board_prep_source_pack
    ON board_preparation_pack_source(pack_id);

-- Pack content, identity, generation metadata and provenance never change. Only
-- lifecycle fields may be updated by the confirmation workflow.
CREATE TRIGGER IF NOT EXISTS trg_exec_prep_immutable_content
BEFORE UPDATE ON executive_preparation_pack
WHEN NEW.ulid IS NOT OLD.ulid
  OR NEW.target_entity_type IS NOT OLD.target_entity_type
  OR NEW.target_entity_ulid IS NOT OLD.target_entity_ulid
  OR NEW.version IS NOT OLD.version
  OR NEW.content IS NOT OLD.content
  OR NEW.content_sha256 IS NOT OLD.content_sha256
  OR NEW.generated_by IS NOT OLD.generated_by
  OR NEW.model IS NOT OLD.model
  OR NEW.prompt_version IS NOT OLD.prompt_version
  OR NEW.generation_metadata IS NOT OLD.generation_metadata
  OR NEW.proposed_by IS NOT OLD.proposed_by
  OR NEW.proposed_at IS NOT OLD.proposed_at
BEGIN
    SELECT RAISE(ABORT, 'executive preparation pack content is immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_board_prep_immutable_content
BEFORE UPDATE ON board_preparation_pack
WHEN NEW.ulid IS NOT OLD.ulid
  OR NEW.board_opportunity_ulid IS NOT OLD.board_opportunity_ulid
  OR NEW.version IS NOT OLD.version
  OR NEW.content IS NOT OLD.content
  OR NEW.content_sha256 IS NOT OLD.content_sha256
  OR NEW.generated_by IS NOT OLD.generated_by
  OR NEW.model IS NOT OLD.model
  OR NEW.prompt_version IS NOT OLD.prompt_version
  OR NEW.generation_metadata IS NOT OLD.generation_metadata
  OR NEW.proposed_by IS NOT OLD.proposed_by
  OR NEW.proposed_at IS NOT OLD.proposed_at
BEGIN
    SELECT RAISE(ABORT, 'board preparation pack content is immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_exec_prep_lifecycle
BEFORE UPDATE ON executive_preparation_pack
WHEN (NEW.status IS NOT OLD.status
   OR NEW.confirmed_by IS NOT OLD.confirmed_by
   OR NEW.confirmed_at IS NOT OLD.confirmed_at
   OR NEW.superseded_at IS NOT OLD.superseded_at)
 AND NOT (OLD.status = 'proposed' AND NEW.status = 'confirmed')
 AND NOT (OLD.status = 'confirmed' AND NEW.status = 'superseded')
BEGIN
    SELECT RAISE(ABORT, 'invalid executive preparation pack lifecycle transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_board_prep_lifecycle
BEFORE UPDATE ON board_preparation_pack
WHEN (NEW.status IS NOT OLD.status
   OR NEW.confirmed_by IS NOT OLD.confirmed_by
   OR NEW.confirmed_at IS NOT OLD.confirmed_at
   OR NEW.superseded_at IS NOT OLD.superseded_at)
 AND NOT (OLD.status = 'proposed' AND NEW.status = 'confirmed')
 AND NOT (OLD.status = 'confirmed' AND NEW.status = 'superseded')
BEGIN
    SELECT RAISE(ABORT, 'invalid board preparation pack lifecycle transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_exec_prep_no_delete
BEFORE DELETE ON executive_preparation_pack
BEGIN SELECT RAISE(ABORT, 'executive preparation pack is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_board_prep_no_delete
BEFORE DELETE ON board_preparation_pack
BEGIN SELECT RAISE(ABORT, 'board preparation pack is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_exec_prep_source_no_update
BEFORE UPDATE ON executive_preparation_pack_source
BEGIN SELECT RAISE(ABORT, 'executive preparation pack source is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_exec_prep_source_no_delete
BEFORE DELETE ON executive_preparation_pack_source
BEGIN SELECT RAISE(ABORT, 'executive preparation pack source is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_board_prep_source_no_update
BEFORE UPDATE ON board_preparation_pack_source
BEGIN SELECT RAISE(ABORT, 'board preparation pack source is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_board_prep_source_no_delete
BEFORE DELETE ON board_preparation_pack_source
BEGIN SELECT RAISE(ABORT, 'board preparation pack source is immutable'); END;

CREATE TABLE IF NOT EXISTS notification_dispatch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    notification_type TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
    fingerprint TEXT NOT NULL UNIQUE CHECK (length(fingerprint) = 64),
    payload TEXT NOT NULL,
    not_before TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    sent_at TEXT,
    CHECK (expires_at > queued_at)
);

CREATE INDEX IF NOT EXISTS idx_notification_dispatch_eligible
    ON notification_dispatch(sent_at, not_before, expires_at, priority);
