-- v1.2: link a logged contact to the engagement it concerned, so relationship
-- activity (contact_log) and pipeline activity (engagements) reconcile.
-- A nullable column add with a column-level FK is a plain ALTER in SQLite.

ALTER TABLE contact_log ADD COLUMN engagement_id INTEGER REFERENCES engagements(id);

CREATE INDEX IF NOT EXISTS idx_contact_log_engagement_id ON contact_log(engagement_id);
