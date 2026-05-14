-- FTS5 search index. Service layer maintains rows.

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5 (
    entity_type,
    entity_ulid,
    primary_text,
    secondary_text,
    tokenize = "unicode61 remove_diacritics 2"
);
