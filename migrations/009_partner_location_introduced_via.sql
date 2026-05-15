-- Add location and introduced_via columns to partners.
ALTER TABLE partners ADD COLUMN location TEXT;
ALTER TABLE partners ADD COLUMN introduced_via TEXT;
