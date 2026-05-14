"""Markdown import round-trip + idempotency tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.services import ServiceContext
from src.services.export_service import ExportService
from src.services.import_service import ImportService

FIXTURE = Path("tests/fixtures/sample-ledger.md")


@pytest.fixture
def ctx(db):
    return ServiceContext(conn=db, actor="FF", transport="cli")


def test_initial_import_creates_everything(ctx):
    md = FIXTURE.read_text()
    summary = ImportService.import_markdown(ctx, md)
    assert summary.firms_created == 2
    assert summary.partners_created == 2
    assert summary.contacts_imported == 3
    assert summary.contacts_skipped == 0
    assert summary.errors == []


def test_second_import_is_idempotent(ctx):
    md = FIXTURE.read_text()
    ImportService.import_markdown(ctx, md)
    second = ImportService.import_markdown(ctx, md)
    assert second.firms_created == 0
    assert second.partners_created == 0
    assert second.contacts_imported == 0
    assert second.contacts_skipped >= 3  # all three previously-seen contacts skipped


def test_overwrite_existing_re_updates_without_duplicating(ctx):
    md = FIXTURE.read_text()
    ImportService.import_markdown(ctx, md)
    third = ImportService.import_markdown(ctx, md, overwrite_existing=True)
    assert third.firms_updated >= 2
    assert third.partners_updated >= 2
    assert third.contacts_imported == 0
    assert third.contacts_skipped >= 3


def test_round_trip_through_export(ctx, tmp_path):
    md = FIXTURE.read_text()
    ImportService.import_markdown(ctx, md)
    exported = ExportService.export_to_markdown(ctx)
    assert "TML Partners" in exported
    assert "Spencer Stuart" in exported

    # Importing the exported markdown into a fresh DB should re-create
    # the same shape, and re-importing it twice should be a no-op.
    import sqlite3
    fresh = sqlite3.connect(":memory:", isolation_level=None)
    fresh.row_factory = sqlite3.Row
    fresh.execute("PRAGMA foreign_keys = ON")
    for m in sorted(Path("migrations").glob("*.sql")):
        fresh.executescript(m.read_text())
    fresh_ctx = ServiceContext(conn=fresh, actor="FF", transport="cli")

    first = ImportService.import_markdown(fresh_ctx, exported)
    second = ImportService.import_markdown(fresh_ctx, exported)
    assert first.contacts_imported == 3
    assert second.contacts_imported == 0
    fresh.close()
