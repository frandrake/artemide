-- 031: board appointment classification and governance/due-diligence profile.
--
-- The executive and board domains are already structurally isolated. These
-- fields make the distinctions inside the board domain explicit, especially
-- the legal difference between statutory appointments and advisory seats.

ALTER TABLE board_opportunity ADD COLUMN appointment_category TEXT
    CHECK (appointment_category IN (
        'ned_unspecified', 'independent_ned', 'non_independent_ned',
        'board_chair', 'senior_independent_director', 'committee_chair',
        'committee_member', 'trustee', 'advisory_board', 'editorial_board',
        'other_board'
    ));

ALTER TABLE board_opportunity ADD COLUMN fiduciary_status TEXT NOT NULL
    DEFAULT 'requires_confirmation'
    CHECK (fiduciary_status IN (
        'statutory_fiduciary', 'contractual_non_fiduciary',
        'requires_confirmation'
    ));

ALTER TABLE board_opportunity ADD COLUMN legal_entity TEXT;
ALTER TABLE board_opportunity ADD COLUMN time_commitment_days INTEGER
    CHECK (time_commitment_days IS NULL OR time_commitment_days >= 0);
ALTER TABLE board_opportunity ADD COLUMN term_length_months INTEGER
    CHECK (term_length_months IS NULL OR term_length_months > 0);
ALTER TABLE board_opportunity ADD COLUMN annual_fee_gbp INTEGER
    CHECK (annual_fee_gbp IS NULL OR annual_fee_gbp >= 0);
ALTER TABLE board_opportunity ADD COLUMN committee_expectations TEXT;
ALTER TABLE board_opportunity ADD COLUMN independence_requirement TEXT;
ALTER TABLE board_opportunity ADD COLUMN liability_indemnity_notes TEXT;
ALTER TABLE board_opportunity ADD COLUMN do_insurance_status TEXT NOT NULL
    DEFAULT 'pending'
    CHECK (do_insurance_status IN ('confirmed', 'not_confirmed', 'pending'));
ALTER TABLE board_opportunity ADD COLUMN conflicts_notes TEXT;
ALTER TABLE board_opportunity ADD COLUMN due_diligence_notes TEXT;
ALTER TABLE board_opportunity ADD COLUMN next_step_due_date DATE;

-- Conservative backfill: never infer independence or statutory status from a
-- legacy "NED" label. Advisory roles are the one safe legal distinction.
UPDATE board_opportunity
SET appointment_category = CASE role
    WHEN 'ned' THEN 'ned_unspecified'
    WHEN 'sid' THEN 'senior_independent_director'
    WHEN 'committee' THEN 'committee_member'
    WHEN 'trustee' THEN 'trustee'
    WHEN 'adviser' THEN 'advisory_board'
    ELSE appointment_category
END
WHERE appointment_category IS NULL;

UPDATE board_opportunity
SET fiduciary_status = 'contractual_non_fiduciary'
WHERE appointment_category IN ('advisory_board', 'editorial_board');

CREATE INDEX IF NOT EXISTS idx_board_opportunity_appointment_category
    ON board_opportunity(appointment_category) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_board_opportunity_next_step_due_date
    ON board_opportunity(next_step_due_date) WHERE deleted_at IS NULL;
