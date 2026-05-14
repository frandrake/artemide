"""Idempotent seed for the firm directory and value-exchange calendar.

Per CLAUDE.md: NED-tier firms are NOT seeded (those relationships start
from referrals rather than the directory). Partners are never seeded.

Usage:
    uv run python scripts/seed_firms.py
    docker compose exec artemide uv run python scripts/seed_firms.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Allow `python scripts/seed_firms.py` to import `src.*` when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402
from src.models import CalendarStatus, FirmTier, RelationshipState  # noqa: E402
from src.repository import firms as firms_repo  # noqa: E402
from src.services import ServiceContext  # noqa: E402
from src.services.firms_service import FirmsService  # noqa: E402
from src.services.planning_service import PlanningService  # noqa: E402


@dataclass(frozen=True)
class SeedFirm:
    name: str
    tier: FirmTier
    region: str
    state: RelationshipState
    notes: str | None = None


SEED_FIRMS: tuple[SeedFirm, ...] = (
    # ----- primary tier -----
    SeedFirm("Spencer Stuart", FirmTier.primary, "Global", RelationshipState.cold,
             "Largest CMO franchise globally. Top priority for warm introduction."),
    SeedFirm("Heidrick & Struggles", FirmTier.primary, "Global", RelationshipState.cold,
             "Strong B2B CMO franchise. Transformation-anchored."),
    SeedFirm("Russell Reynolds", FirmTier.primary, "Global", RelationshipState.cold,
             "Strong on transformation CMO mandates. Tech and FS overweight."),
    SeedFirm("Egon Zehnder", FirmTier.primary, "Europe", RelationshipState.cold,
             "Strongest in continental Europe. Chair-track useful for NED."),
    SeedFirm("Korn Ferry", FirmTier.primary, "Global", RelationshipState.cold,
             "Useful for comp benchmarking. Broad coverage."),

    # ----- specialist tier -----
    SeedFirm("TML Partners", FirmTier.specialist, "London", RelationshipState.warm,
             "Marketing leadership specialist. Only existing warm tie."),
    SeedFirm("Odgers Berndtson", FirmTier.specialist, "London", RelationshipState.cold,
             None),
    SeedFirm("MBS Group", FirmTier.specialist, "London", RelationshipState.cold,
             "Consumer-leaning. Lower priority given B2B focus."),
    SeedFirm("True Search", FirmTier.specialist, "Global", RelationshipState.cold,
             "Tech-leaning. Relevant for enterprise SaaS optionality."),
    SeedFirm("Eric Salmon & Partners", FirmTier.specialist, "Europe", RelationshipState.cold,
             "Italian heritage relevant. European optionality."),
    SeedFirm("Acertitude", FirmTier.specialist, "Global", RelationshipState.cold,
             "Emerging mid-market. PE portfolio CMO mandates."),
)


# Q1/Q3/Q4 topics are reasonable placeholders consistent with the brand
# voice; Q2 matches the value-exchange topic surfaced in the design
# transcripts. Adjust freely after seeding via /api/v1/planning/quarter-topic.
SEED_QUARTERS: tuple[tuple[int, int, str, CalendarStatus], ...] = (
    (2026, 1, "Foundational outreach: warm-tie briefs across primary tier", CalendarStatus.complete),
    (2026, 2, "Agentic CMO themes: chapter previews for the v2 manuscript launch", CalendarStatus.in_progress),
    (2026, 3, "Mid-year reciprocity review and re-engagement of dormant ties", CalendarStatus.planned),
    (2026, 4, "Year-end outlook calls and NED-track exploration", CalendarStatus.planned),
)


def seed_firms(ctx: ServiceContext) -> tuple[int, int]:
    """Returns (new_count, existing_count)."""
    new_count = 0
    existing_count = 0
    for f in SEED_FIRMS:
        existing = firms_repo.get_firm_by_name(ctx.conn, f.name)
        if existing is not None:
            print(f"  [exists]  {f.name}")
            existing_count += 1
            continue
        FirmsService._create_internal(
            ctx,
            name=f.name,
            tier=f.tier,
            region=f.region,
            relationship_state=f.state,
            notes_summary=f.notes,
        )
        print(f"  [created] {f.name} · {f.tier.value} · {f.region} · {f.state.value}")
        new_count += 1
    return new_count, existing_count


def seed_quarter_topics(ctx: ServiceContext) -> tuple[int, int]:
    """Returns (new_or_updated, unchanged)."""
    changed = 0
    unchanged = 0
    for year, quarter, topic, status in SEED_QUARTERS:
        existing = PlanningService.get_quarter_topic(ctx, year=year, quarter=quarter)
        if existing is not None and existing.topic == topic and existing.status == status:
            print(f"  [exists]  Q{quarter} {year}")
            unchanged += 1
            continue
        PlanningService.set_quarter_topic(
            ctx, year=year, quarter=quarter, topic=topic, status=status,
        )
        print(f"  [set]     Q{quarter} {year}: {topic}")
        changed += 1
    return changed, unchanged


def main() -> int:
    init_db()
    conn = get_connection()
    try:
        ctx = ServiceContext(conn=conn, actor="FF", transport="system")
        print("Seeding firms…")
        new_firms, existing_firms = seed_firms(ctx)
        print("Seeding quarter topics…")
        new_qs, existing_qs = seed_quarter_topics(ctx)
    finally:
        conn.close()

    print(
        f"\n{new_firms} firm(s) seeded, {existing_firms} already existed. "
        f"{new_qs} quarter topic(s) updated, {existing_qs} unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
