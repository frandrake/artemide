"""Verify the headhunter seed — row counts and spot-checks.

Usage:
    uv run python scripts/verify_seed.py
    docker compose exec artemide uv run python scripts/verify_seed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402


def verify() -> bool:
    init_db()
    conn = get_connection()
    ok = True

    def check(label: str, query: str, args: tuple = (), expected_min: int = 1) -> None:
        nonlocal ok
        count = conn.execute(query, args).fetchone()[0]
        status = "✓" if count >= expected_min else "✗"
        if count < expected_min:
            ok = False
        print(f"  {status}  {label}: {count} (expected ≥ {expected_min})")

    def spot(label: str, query: str, args: tuple = ()) -> None:
        row = conn.execute(query, args).fetchone()
        status = "✓" if row else "✗"
        nonlocal ok
        if not row:
            ok = False
        val = dict(row) if row else "(not found)"
        print(f"  {status}  {label}: {val}")

    print("\n── Row counts ─────────────────────────────────────────────────────")
    check("Total firms", "SELECT COUNT(*) FROM firms WHERE deleted_at IS NULL", expected_min=13)
    check("Tier-1 global firms", "SELECT COUNT(*) FROM firms WHERE market_tier='tier-1-global'", expected_min=5)
    check("Specialist boutique firms", "SELECT COUNT(*) FROM firms WHERE market_tier='specialist-boutique'", expected_min=7)
    check("Total active partners", "SELECT COUNT(*) FROM partners WHERE deleted_at IS NULL", expected_min=28)
    check("HIGH strategic relevance partners", "SELECT COUNT(*) FROM partners WHERE strategic_relevance='HIGH'", expected_min=10)
    check("NED gateway partners", "SELECT COUNT(*) FROM partners WHERE ned_gateway=1", expected_min=8)
    check("Partner notes (seed)", "SELECT COUNT(*) FROM notes WHERE entity_type='partner' AND body LIKE '[headhunter-seed-v1]%'", expected_min=25)
    check("Engagement calendar entries", "SELECT COUNT(*) FROM engagement_calendar", expected_min=25)
    check("Track-1 entries", "SELECT COUNT(*) FROM engagement_calendar WHERE track='track-1'", expected_min=5)
    check("Track-5 NED entries", "SELECT COUNT(*) FROM engagement_calendar WHERE track='track-5'", expected_min=4)
    check("Track-6 entries", "SELECT COUNT(*) FROM engagement_calendar WHERE track='track-6'", expected_min=5)
    check("Audit log entries (seed)", "SELECT COUNT(*) FROM audit_log WHERE actor='seed'", expected_min=30)

    print("\n── Spot checks ────────────────────────────────────────────────────")
    spot("Spencer Stuart has strategic_fit=HIGH",
         "SELECT name, strategic_fit, market_tier FROM firms WHERE name='Spencer Stuart'")
    spot("Grant Duncan exists at Korn Ferry with HIGH relevance",
         "SELECT p.name, p.strategic_relevance, p.ned_gateway FROM partners p "
         "JOIN firms f ON f.id=p.firm_id WHERE p.name='Grant Duncan' AND f.name='Korn Ferry'")
    spot("Greg Hodge exists at RRA",
         "SELECT p.name, p.strategic_relevance FROM partners p JOIN firms f ON f.id=p.firm_id "
         "WHERE p.name='Greg Hodge' AND f.name LIKE 'Russell Reynolds%'")
    spot("Kit Bingham is NED gateway",
         "SELECT name, ned_gateway FROM partners WHERE name='Kit Bingham'")
    spot("Kate Grussing CBE at Sapphire Partners",
         "SELECT p.name, f.name as firm FROM partners p JOIN firms f ON f.id=p.firm_id "
         "WHERE p.name='Kate Grussing CBE'")
    spot("Engagement calendar Track-1 week-4 entry",
         "SELECT title, track, due_date FROM engagement_calendar "
         "WHERE track='track-1' AND title LIKE '%Send outreach%Greg Hodge%'")
    spot("Grace Blue Partnership created",
         "SELECT name, market_tier FROM firms WHERE name='Grace Blue Partnership'")
    spot("Simon Bassett warm intro angle populated",
         "SELECT name, SUBSTR(warm_intro_angle, 1, 60) as angle FROM partners WHERE name='Simon Bassett'")

    print("\n── Field coverage ─────────────────────────────────────────────────")
    firms_missing = conn.execute(
        "SELECT name FROM firms WHERE market_tier IS NULL AND deleted_at IS NULL ORDER BY name"
    ).fetchall()
    if firms_missing:
        print(f"  ✗  Firms missing market_tier: {[r[0] for r in firms_missing]}")
        ok = False
    else:
        print("  ✓  All active firms have market_tier set")

    # Only check partners with prior_career set (i.e., seeded by this script).
    partners_missing = conn.execute(
        "SELECT name FROM partners WHERE strategic_relevance IS NULL "
        "AND prior_career IS NOT NULL AND deleted_at IS NULL ORDER BY name"
    ).fetchall()
    if partners_missing:
        print(f"  ✗  Seeded partners missing strategic_relevance: {[r[0] for r in partners_missing]}")
        ok = False
    else:
        print("  ✓  All seeded partners have strategic_relevance set")

    conn.close()
    print()
    return ok


if __name__ == "__main__":
    passed = verify()
    if passed:
        print("All checks passed.")
    else:
        print("Some checks FAILED — re-run seed_headhunters.py and retry.", file=sys.stderr)
    raise SystemExit(0 if passed else 1)
