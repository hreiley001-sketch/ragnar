#!/usr/bin/env bash
# Start a local n8n for RAGNAR automation.
# Upstream source: https://github.com/n8n-io/n8n.git (we run the published npm package).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME="$ROOT/runtime"
NODE22="/home/ubuntu/.nvm/versions/node/v22.22.2/bin"
export PATH="$NODE22:$PATH"

if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>22||(a===22&&b>=22)?0:1)'; then
  echo "n8n needs Node >= 22.22 (found $(node -v))." >&2
  exit 1
fi

if [[ ! -x "$RUNTIME/node_modules/n8n/bin/n8n" ]]; then
  echo "Installing n8n into $RUNTIME …"
  mkdir -p "$RUNTIME"
  cd "$RUNTIME"
  [[ -f package.json ]] || npm init -y >/dev/null
  npm install n8n@latest --no-fund --no-audit
fi

export N8N_PORT="${N8N_PORT:-5678}"
export N8N_HOST="${N8N_HOST:-0.0.0.0}"
export N8N_PROTOCOL="${N8N_PROTOCOL:-http}"
export N8N_EDITOR_BASE_URL="${N8N_EDITOR_BASE_URL:-http://127.0.0.1:${N8N_PORT}}"
export N8N_WEBHOOK_URL="${N8N_WEBHOOK_URL:-http://127.0.0.1:${N8N_PORT}/}"
export N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-ragnar-local-n8n-dev-key-change-me}"
export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$RUNTIME/.n8n}"
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_PERSONALIZATION_ENABLED=false
export N8N_VERSION_NOTIFICATIONS_ENABLED=false
mkdir -p "$N8N_USER_FOLDER"

echo "n8n UI:      http://127.0.0.1:${N8N_PORT}"
echo "Webhook:     http://127.0.0.1:${N8N_PORT}/webhook/ragnar-events"
echo "Upstream:    https://github.com/n8n-io/n8n.git"
exec node "$RUNTIME/node_modules/n8n/bin/n8n" start
