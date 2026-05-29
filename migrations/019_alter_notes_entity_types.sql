-- v1.2: extend notes.entity_type CHECK to allow 'org' and 'engagement'.
-- SQLite cannot ALTER a CHECK constraint, so rebuild the table. notes is a
-- leaf table (no FK points at it, it points at nothing), so the rebuild is
-- safe inside the migration runner's transaction without toggling
-- PRAGMA foreign_keys (which the single-transaction runner cannot do anyway).

DROP TABLE IF EXISTS notes_rebuild;

CREATE TABLE notes_rebuild (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('firm', 'partner', 'org', 'engagement')),
    entity_id TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO notes_rebuild (id, ulid, entity_type, entity_id, body, created_at)
    SELECT id, ulid, entity_type, entity_id, body, created_at FROM notes;

DROP TABLE notes;
ALTER TABLE notes_rebuild RENAME TO notes;

CREATE INDEX IF NOT EXISTS idx_notes_entity ON notes(entity_type, entity_id);
