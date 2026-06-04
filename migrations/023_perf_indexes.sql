-- 023: performance indexes for the list/sort/aggregate hot paths.
-- All are covered by existing query shapes (see repository list_* functions);
-- partial indexes mirror the soft-delete predicate so they stay small.

-- messages list: status filter + created_at ordering (routes_messages, MCP list_messages)
CREATE INDEX IF NOT EXISTS idx_messages_status_created
    ON messages(status, created_at DESC);

-- engagements default pipeline sort (list_engagements ORDER BY created_at DESC)
CREATE INDEX IF NOT EXISTS idx_engagements_created
    ON engagements(created_at DESC) WHERE deleted_at IS NULL;

-- engagements fit-sorted view (sort=fit path)
CREATE INDEX IF NOT EXISTS idx_engagements_fit
    ON engagements(fit_score DESC) WHERE deleted_at IS NULL;

-- audit explorer/report: entity timeline ordering (existing idx omits timestamp)
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_ts
    ON audit_log(entity_type, entity_id, timestamp DESC);

-- reciprocity / value aggregation over contact_log (covering, avoids row lookups)
CREATE INDEX IF NOT EXISTS idx_contact_log_partner_values
    ON contact_log(partner_id, value_given, value_received);
