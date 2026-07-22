# Docker Compose notes for RAGNAR
# Tool upstream: https://github.com/docker/compose.git
# CLI: `docker compose` (Compose V2 plugin) — same project as the git repo above.

## Quick start

```bash
# Install Compose V2 (Ubuntu example)
sudo apt-get install -y docker.io docker-compose-v2
# or binary from: https://github.com/docker/compose/releases

cp .env.example .env
# Set DATABASE_URL (Supabase Session pooler recommended), ADMIN_TOKEN, etc.

docker compose up --build -d
```

| Service | URL |
|---|---|
| RAGNAR | http://127.0.0.1:8000 |
| n8n | http://127.0.0.1:5678 |
| RAGNAR→n8n webhook (in-network) | http://n8n:5678/webhook/ragnar-events |

After n8n first boot, open the UI, create an owner, then either:

```bash
# from host, against published n8n port
N8N_BASE_URL=http://127.0.0.1:5678 ./integrations/n8n/import-workflow.sh
```

or **Import from file** → `integrations/n8n/ragnar-events.json` and activate it.

Set in `.env` (compose already defaults the in-network URL for the `ragnar` service):

```bash
N8N_WEBHOOK_URL=http://n8n:5678/webhook/ragnar-events
```

Obsidian Local REST API still runs on your desktop (`127.0.0.1:27124`). Point an
n8n HTTP node at it from a runner that can reach your machine, or write vault
files via an n8n filesystem node.

## Useful commands

```bash
docker compose ps
docker compose logs -f ragnar n8n
docker compose down
```
