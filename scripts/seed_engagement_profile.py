"""Idempotent seed for the active engagement_profile (the fit criteria).

Seed values from the plan: comp base floor £250k, total target £500k; accepted
role types and scale bands; hard exclusions; default dimension weights (sum 100).

If an active profile already exists this script is a no-op (it prints the
current one). Re-tuning is done via Settings → Engagement profile, which writes
a new version.

Usage:
    uv run python scripts/seed_engagement_profile.py
    docker compose exec artemide uv run python scripts/seed_engagement_profile.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402
from src.repository import engagement_profile as profile_repo  # noqa: E402
from src.services import transaction  # noqa: E402

SEED = {
    "comp_base_floor_gbp": 250_000,
    "comp_total_target_gbp": 500_000,
    "accepted_role_types": ["cmo", "cmgo", "cco", "transformation"],
    "accepted_scale_bands": ["fortune_500", "global_equivalent"],
    "hard_exclusions": [
        "custodial_brand_only",
        "high_politics",
        "micromanaging_board",
        "performative_visibility",
        "weak_transformation",
    ],
    "weights": {
        "role_type": 20,
        "scale": 15,
        "comp": 20,
        "pertinence": 15,
        "geography": 10,
        "autonomy_signal": 10,
        "politics_signal": 10,
    },
}


def main() -> int:
    init_db()
    conn = get_connection()
    try:
        existing = profile_repo.get_active_profile(conn)
        if existing is not None:
            print(f"  [exists]  active profile v{existing.version} "
                  f"(floor £{existing.comp_base_floor_gbp:,}, target £{existing.comp_total_target_gbp:,})")
            return 0
        with transaction(conn):
            version = profile_repo.max_version(conn) + 1
            profile_repo.insert_profile(conn, version=version, active=True, **SEED)
        print(f"  [created] active engagement_profile v{version}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
