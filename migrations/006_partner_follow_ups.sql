-- Outstanding follow-ups per partner, stored as JSON array of strings.

ALTER TABLE partners ADD COLUMN follow_ups_outstanding TEXT;
