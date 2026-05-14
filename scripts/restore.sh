#!/usr/bin/env bash
# Restore a .db.gz backup into the running artemide container.
# Stops uvicorn (via compose restart) so SQLite WAL doesn't replay over
# the restored file.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <backup-file.db.gz>"
  exit 1
fi

SRC="$1"
if [ ! -f "$SRC" ]; then
  echo "Backup file not found: $SRC"
  exit 1
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

gunzip -c "$SRC" > "$TMP"
docker compose cp "$TMP" artemide:/data/artemide.db.restored
docker compose exec -T artemide sh -c 'mv /data/artemide.db.restored /data/artemide.db'
docker compose restart artemide

echo "Restored from: $SRC"
