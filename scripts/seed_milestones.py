"""Idempotent seed for the five programme milestones along the phase track.

Milestones work back from ARTEMIDE_PROGRAMME_TARGET_DATE (default 2027-04-05).
The Close milestone sits twelve days before the target (Rule 16); Exit is the
target itself. Each milestone is keyed by phase and seeded once.

Usage:
    uv run python scripts/seed_milestones.py
    docker compose exec artemide uv run python scripts/seed_milestones.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402
from src.repository import programme as programme_repo  # noqa: E402
from src.services import transaction  # noqa: E402


def _target_date() -> date:
    raw = os.environ.get("ARTEMIDE_PROGRAMME_TARGET_DATE", "2027-04-05")
    return date.fromisoformat(raw)


def _milestones(target: date) -> list[tuple[str, str, date, str]]:
    """(phase, label, target_date, metric_note) working back from target."""
    return [
        ("build", "Infrastructure, fit profile and org list live",
         date(target.year - 1, 6, 30), "Profile active; ≥1 org under watch"),
        ("seed", "Relationship seeding across the partner network",
         date(target.year - 1, 9, 30), "≥5 partners at warm/warming"),
        ("run", "Engagements in motion at formal stage",
         date(target.year - 1, 12, 31), "≥2 engagements at formal/final"),
        ("close", "Offer / decision in hand",
         target - timedelta(days=12), "≥1 engagement at offer/decision"),
        ("exit", "Programme objective met",
         target, "Decision made"),
    ]


def main() -> int:
    init_db()
    conn = get_connection()
    target = _target_date()
    created = 0
    existing = 0
    try:
        with transaction(conn):
            for phase, label, when, metric in _milestones(target):
                if programme_repo.get_milestone_by_phase(conn, phase) is not None:
                    print(f"  [exists]  {phase}")
                    existing += 1
                    continue
                programme_repo.insert_milestone(
                    conn, phase=phase, label=label, target_date=when, metric_note=metric
                )
                print(f"  [created] {phase} · {when.isoformat()} · {metric}")
                created += 1
    finally:
        conn.close()
    print(f"\n{created} milestone(s) seeded, {existing} already existed. Target: {target.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
