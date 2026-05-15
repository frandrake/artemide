"""SQLite connection helpers and migration runner."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _default_db_path() -> str:
    return os.environ.get("ARTEMIDE_DB_PATH", "./data/artemide.db")


# Kept for backwards compatibility (e.g. log messages); always prefer
# `_default_db_path()` for fresh reads at call time.
DB_PATH = _default_db_path()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or _default_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY,"
        "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def init_db(db_path: str | None = None, migrations_dir: Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        _ensure_migrations_table(conn)
        applied = _applied_versions(conn)
        migrations = sorted((migrations_dir or MIGRATIONS_DIR).glob("*.sql"))
        for migration in migrations:
            version = migration.stem
            if version in applied:
                continue
            sql = migration.read_text()
            conn.executescript("BEGIN; " + sql + "; COMMIT;")
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Migrations applied to {_default_db_path()}")
