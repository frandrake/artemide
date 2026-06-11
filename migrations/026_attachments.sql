-- v1.3: attachments — uploaded files stored as BLOBs inside SQLite so they are
-- captured by `sqlite3 .backup` (scripts/backup.sh, /api/v1/admin/backup) like
-- every other row. Bytes live in `content`; the metadata read paths never
-- SELECT it (repository/attachments.py splits _META_COLUMNS from get_content).
-- Soft-deletable; bounded by a service-level mime allowlist + 25 MB cap.

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('firm', 'partner', 'org', 'engagement', 'interview')),
    entity_id TEXT NOT NULL,                 -- target ULID
    kind TEXT NOT NULL
        CHECK (kind IN ('cv', 'profile', 'job_spec', 'transcript_file', 'reference', 'other')),
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    content BLOB NOT NULL,
    uploaded_by TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_entity
    ON attachments(entity_type, entity_id) WHERE deleted_at IS NULL;

-- Idempotency: re-uploading identical bytes to the same target returns the
-- existing row instead of creating a duplicate (enforced in the service).
CREATE UNIQUE INDEX IF NOT EXISTS uq_attachments_entity_sha
    ON attachments(entity_type, entity_id, sha256) WHERE deleted_at IS NULL;
