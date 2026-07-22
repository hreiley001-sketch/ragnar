#!/usr/bin/env bash
# Create/activate the RAGNAR events workflow in a running local n8n (REST).
# Prefer this over the CLI on n8n 2.x single-process mode.
set -euo pipefail
BASE="${N8N_BASE_URL:-http://127.0.0.1:5678}"
EMAIL="${N8N_OWNER_EMAIL:-admin@ragnarips.com}"
PASS="${N8N_OWNER_PASSWORD:-RagnarN8n!2026}"
WF_JSON="$(cd "$(dirname "$0")" && pwd)/ragnar-events.json"
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT

curl -sf -c "$COOKIE" -b "$COOKIE" "$BASE/rest/login" \
  -H 'Content-Type: application/json' \
  -d "{\"emailOrLdapLoginId\":\"$EMAIL\",\"password\":\"$PASS\"}" >/dev/null

python3 - "$WF_JSON" <<'PY' > /tmp/n8n-create-payload.json
import json, sys
wf = json.load(open(sys.argv[1]))
json.dump({
    "name": wf.get("name") or "RAGNAR → Obsidian events",
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {"executionOrder": "v1"},
}, sys.stdout)
PY

CREATED="$(curl -sf -b "$COOKIE" -c "$COOKIE" "$BASE/rest/workflows" \
  -H 'Content-Type: application/json' --data-binary @/tmp/n8n-create-payload.json)"
WF_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])' <<<"$CREATED")"
VER="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["versionId"])' <<<"$CREATED")"

curl -sf -b "$COOKIE" -c "$COOKIE" -X POST "$BASE/rest/workflows/$WF_ID/activate" \
  -H 'Content-Type: application/json' \
  -d "{\"versionId\":\"$VER\"}" >/dev/null

echo "Workflow $WF_ID active."
echo "Set RAGNAR: N8N_WEBHOOK_URL=$BASE/webhook/ragnar-events"
