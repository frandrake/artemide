-- 024: widen contact_log uniqueness to include initiated_by.
-- The old key (partner_id, contact_date, channel) collapsed two genuinely
-- distinct contacts on the same day/channel — e.g. an outbound email ('me')
-- and the inbound reply ('them') — silently dropping the second. The new key
-- is a strict superset, so no existing row can violate it.

DROP INDEX IF EXISTS uq_contact_log_partner_date_channel;

CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_log_partner_date_channel_initiator
    ON contact_log(partner_id, contact_date, channel, initiated_by);
