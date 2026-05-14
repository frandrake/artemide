#!/usr/bin/env bash
# Host-side backup: runs sqlite3 .backup inside the artemide container
# (atomic w.r.t. concurrent writes), copies the resulting file out to
# ./backups/, gzips it, and prunes anything older than 30 days.
#
# Triggered manually or via cron (see docs/operations.md). Distinct from
# scripts/admin-backup.sh, which is the in-container script the REST
# /api/v1/admin/backup endpoint shells out to.

set -euo pipefail

cd "$(dirname "$0")/.."
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

docker compose exec -T artemide sqlite3 /data/artemide.db ".backup '/data/backup-${TS}.db'"
docker compose cp "artemide:/data/backup-${TS}.db" "$BACKUP_DIR/backup-${TS}.db"
docker compose exec -T artemide rm "/data/backup-${TS}.db"

gzip "$BACKUP_DIR/backup-${TS}.db"
find "$BACKUP_DIR" -name "backup-*.db.gz" -mtime +30 -delete

echo "Backup: $BACKUP_DIR/backup-${TS}.db.gz"
