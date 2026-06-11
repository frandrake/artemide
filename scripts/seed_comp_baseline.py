"""Idempotent seed for the baseline compensation scenario.

Creates "Current — S&P Global" with is_baseline=1 and all comp fields NULL
(placeholders — fill the real figures via the Compensation page or
upsert_comp_scenario). No-op if a live baseline already exists.

Usage:
    uv run python scripts/seed_comp_baseline.py
    docker compose exec artemide uv run python scripts/seed_comp_baseline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection, init_db  # noqa: E402
from src.repository import comp_scenarios as comp_repo  # noqa: E402
from src.services import transaction  # noqa: E402

BASELINE_NAME = "Current — S&P Global"


def main() -> int:
    init_db()
    conn = get_connection()
    try:
        existing = comp_repo.get_baseline(conn)
        if existing is not None:
            print(f"  [exists]  baseline scenario '{existing.name}' ({existing.ulid})")
            return 0
        with transaction(conn):
            scenario = comp_repo.insert_scenario(
                conn, name=BASELINE_NAME, status="current", is_baseline=True,
            )
        print(f"  [created] baseline scenario '{scenario.name}' ({scenario.ulid})")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
