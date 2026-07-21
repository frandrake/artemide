"""Hard separation and governance metadata for executive vs board opportunities."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.models import BoardOpportunityUpdateInput, UpsertBoardOpportunityInput
from src.services import ServiceContext
from src.services.board_opportunities_service import BoardOpportunitiesService
from src.services.exceptions import ValidationError


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="cli")


def test_advisory_board_is_explicitly_non_fiduciary(ctx):
    opportunity = BoardOpportunitiesService.upsert(
        ctx,
        UpsertBoardOpportunityInput(
            organisation="Advisory Co",
            appointment_category="advisory_board",
        ),
    )

    assert opportunity.appointment_category.value == "advisory_board"
    assert opportunity.fiduciary_status.value == "contractual_non_fiduciary"


def test_advisory_board_cannot_be_presented_as_statutory_fiduciary(ctx):
    with pytest.raises(ValidationError, match="non-fiduciary"):
        BoardOpportunitiesService.upsert(
            ctx,
            UpsertBoardOpportunityInput(
                organisation="Misclassified Co",
                appointment_category="advisory_board",
                fiduciary_status="statutory_fiduciary",
            ),
        )


def test_board_governance_profile_round_trips_and_is_audited(ctx, db):
    opportunity = BoardOpportunitiesService.upsert(
        ctx,
        UpsertBoardOpportunityInput(
            organisation="Governed plc",
            appointment_category="independent_ned",
            fiduciary_status="statutory_fiduciary",
            legal_entity="Governed plc (England & Wales 01234567)",
            time_commitment_days=24,
            term_length_months=36,
            annual_fee_gbp=85_000,
            committee_expectations="Audit and technology committees",
            independence_requirement="UK Corporate Governance Code independent",
            liability_indemnity_notes="Deed of indemnity to review",
            do_insurance_status="pending",
            conflicts_notes="Employer clearance required",
            due_diligence_notes="Review latest annual report and audit findings",
            next_step_due_date="2026-08-01",
        ),
    )

    assert opportunity.time_commitment_days == 24
    assert opportunity.annual_fee_gbp == 85_000
    assert opportunity.next_step_due_date.isoformat() == "2026-08-01"

    updated = BoardOpportunitiesService.update_fields(
        ctx,
        opportunity.ulid,
        BoardOpportunityUpdateInput(do_insurance_status="confirmed"),
    )
    assert updated.do_insurance_status.value == "confirmed"

    cleared = BoardOpportunitiesService.update_fields(
        ctx,
        opportunity.ulid,
        BoardOpportunityUpdateInput(
            legal_entity=None,
            annual_fee_gbp=None,
            next_step_due_date=None,
        ),
    )
    assert cleared.legal_entity is None
    assert cleared.annual_fee_gbp is None
    assert cleared.next_step_due_date is None

    rows = db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE entity_type = 'board_opportunity' AND entity_id = ?",
        (opportunity.ulid,),
    ).fetchone()[0]
    assert rows == 3


def test_migration_backfills_legacy_role_without_inventing_ned_independence(tmp_path):
    conn = sqlite3.connect(tmp_path / "legacy.db", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrations = sorted(Path("migrations").glob("*.sql"))
    for migration in migrations:
        if migration.name >= "031_board_governance.sql":
            break
        conn.executescript(migration.read_text())

    conn.execute(
        "INSERT INTO board_opportunity (ulid, organisation, role) VALUES (?, ?, ?)",
        ("01LEGACYNED00000000000000", "Legacy NED plc", "ned"),
    )
    conn.execute(
        "INSERT INTO board_opportunity (ulid, organisation, role) VALUES (?, ?, ?)",
        ("01LEGACYADV00000000000000", "Legacy Advisory Ltd", "adviser"),
    )

    migration = Path("migrations/031_board_governance.sql")
    conn.executescript(migration.read_text())
    rows = conn.execute(
        "SELECT organisation, appointment_category, fiduciary_status "
        "FROM board_opportunity ORDER BY organisation"
    ).fetchall()
    conn.close()

    assert dict(rows[0]) == {
        "organisation": "Legacy Advisory Ltd",
        "appointment_category": "advisory_board",
        "fiduciary_status": "contractual_non_fiduciary",
    }
    assert dict(rows[1]) == {
        "organisation": "Legacy NED plc",
        "appointment_category": "ned_unspecified",
        "fiduciary_status": "requires_confirmation",
    }
