#!/bin/sh
# Phase 3 placeholder backup script. Phase 6+ will replace with a real
# restic-based implementation. Outputs the backup filename on stdout.
set -eu
TIMESTAMP="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${ARTEMIDE_BACKUP_DIR:-/data/backups}"
mkdir -p "$OUT_DIR"
DB_PATH="${ARTEMIDE_DB_PATH:-/data/artemide.db}"
OUT_FILE="$OUT_DIR/artemide-$TIMESTAMP.db"
if [ -f "$DB_PATH" ]; then
  cp "$DB_PATH" "$OUT_FILE"
fi
echo "$OUT_FILE"
