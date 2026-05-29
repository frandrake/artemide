-- v1.2: organisations and engagements join the FTS5 search_index.
--
-- The v1.1 search_index (migration 004) is a generic, service-maintained FTS5
-- table (entity_type, entity_ulid, primary_text, secondary_text) with no sync
-- triggers — SearchService writes rows directly. v1.2 follows the same pattern:
-- SearchService indexes 'org' (name + pertinence_note) and 'engagement'
-- (role_title + org name + dossier note bodies) rows. No structural change is
-- required; this migration is a contiguous version marker.

SELECT 1;
