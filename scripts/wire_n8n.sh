#!/usr/bin/env bash
# One-shot wiring of the Artemide n8n automation layer.
#
# Does, in order:
#   1. Issues a fresh Artemide bot token (retires the previous one).
#   2. Imports n8n credentials: the Artemide header-auth credential gets the
#      fresh bot token; a Telegram credential is created from .digest.env;
#      the Claude credential is (re)set only when ANTHROPIC_API_KEY is passed.
#   3. Imports the updated cadence + rollup workflow JSONs from n8n/.
#   4. Activates both workflows and restarts the n8n container.
#   5. Runs the rollup once — a Friday read-out should land on Telegram.
#
# Usage:
#   bash scripts/wire_n8n.sh
#   ANTHROPIC_API_KEY=sk-ant-... bash scripts/wire_n8n.sh
set -euo pipefail

ART_DIR=/root/artemide
ART_URL=http://127.0.0.1:47600

# --- 1. fresh bot token -------------------------------------------------
OWNER_TOKEN=$(grep -m1 '^ARTEMIDE_API_TOKEN=' "$ART_DIR/.env" | cut -d= -f2-)
BOT_TOKEN=$(curl -sf -X POST "$ART_URL/api/v1/admin/issue-bot-token" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["new_token"])')
echo "· bot token issued"

# --- 2. credentials import file -----------------------------------------
# shellcheck disable=SC1091
source "$ART_DIR/.digest.env" # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

BOT_TOKEN="$BOT_TOKEN" TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
python3 - "$TMP/creds.json" << 'PYEOF'
import json, os, sys

creds = [
    {
        "id": "mQGb3Y3d2iePVpMX",
        "name": "Header Auth account",
        "type": "httpHeaderAuth",
        "data": {"name": "Authorization", "value": f"Bearer {os.environ['BOT_TOKEN']}"},
    },
    {
        "id": "artemide-telegram",
        "name": "Telegram · Deddagpt",
        "type": "telegramApi",
        "data": {
            "accessToken": os.environ["TELEGRAM_BOT_TOKEN"],
            "baseUrl": "https://api.telegram.org",
        },
    },
]
if os.environ.get("ANTHROPIC_API_KEY"):
    creds.append({
        "id": "jw8mJ5QHwqxObbFo",
        "name": "Header Auth account 2",
        "type": "httpHeaderAuth",
        "data": {"name": "x-api-key", "value": os.environ["ANTHROPIC_API_KEY"]},
    })
with open(sys.argv[1], "w") as f:
    json.dump(creds, f)
print(f"· credentials file built ({len(creds)} credentials)")
PYEOF
chmod 600 "$TMP/creds.json"

# --- 3. import into n8n ---------------------------------------------------
docker cp "$TMP/creds.json" n8n:/tmp/creds.json
docker cp "$ART_DIR/n8n/02_cadence.json" n8n:/tmp/02_cadence.json
docker cp "$ART_DIR/n8n/07_rollup.json" n8n:/tmp/07_rollup.json
docker exec -u node n8n n8n import:credentials --input=/tmp/creds.json
docker exec -u node n8n n8n import:workflow --input=/tmp/02_cadence.json
docker exec -u node n8n n8n import:workflow --input=/tmp/07_rollup.json
docker exec -u node n8n rm -f /tmp/creds.json /tmp/02_cadence.json /tmp/07_rollup.json
echo "· credentials + workflows imported"

# --- 4. activate + restart -----------------------------------------------
docker exec -u node n8n n8n update:workflow --id=artemide-cadence --active=true
docker exec -u node n8n n8n update:workflow --id=artemide-rollup --active=true
docker restart n8n
echo "· workflows activated, n8n restarting"
sleep 20

# --- 5. live test: run the rollup once ------------------------------------
echo "· executing Artemide · Rollup (expect a Telegram message)…"
docker exec -u node n8n n8n execute --id=artemide-rollup || {
  echo "!! rollup execution failed — check: docker logs n8n --tail 50"; exit 1; }
echo "· executing Artemide · Cadence (dry: no partners due today)…"
docker exec -u node n8n n8n execute --id=artemide-cadence || {
  echo "!! cadence execution failed — check: docker logs n8n --tail 50"; exit 1; }
echo "✓ n8n wiring complete: cadence (Mon 08:00) + rollup (Fri 16:00) active"
