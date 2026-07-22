# RAGNAR ↔ n8n ↔ Obsidian

Automation bridge so marketplace events and Counsel knowledge flow into your
ops stack. **n8n is never on the FastAPI hot path** — events are enqueued
(Redis list or background HTTP) and return immediately. Obsidian is **docs /
content only**, not a runtime dependency.

Full architecture: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

Upstream n8n: **https://github.com/n8n-io/n8n.git** (we run the published
`n8n` npm package — same project, no need to build the monorepo).

```
RAGNAR  --async enqueue-->  n8n  --write notes-->  Obsidian vault
   |                          |
   +-- (admin export only) ---+  (optional; not request-path)
```

## 0. Run n8n locally (this repo)

Requires **Node ≥ 22.22**.

```bash
cd integrations/n8n
./start.sh
# UI: http://127.0.0.1:5678

./import-workflow.sh   # creates + activates "RAGNAR → Obsidian events"
```

Then set in RAGNAR `.env`:

```bash
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/ragnar-events
```

Or use upstream directly:

```bash
git clone https://github.com/n8n-io/n8n.git
# or: npm install -g n8n && n8n start
```

## 1. Configure RAGNAR

Add to `.env` (never commit secrets):

```bash
# n8n — paste the Production URL from a Webhook node
N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/ragnar-events
# Optional HMAC verification in n8n
N8N_WEBHOOK_SECRET=choose-a-long-random-string

# Obsidian Local REST API plugin (optional; n8n can write files instead)
# Install: obsidian://show-plugin?id=obsidian-local-rest-api
OBSIDIAN_API_URL=https://127.0.0.1:27124
OBSIDIAN_API_KEY=your-obsidian-api-key
OBSIDIAN_VAULT_PREFIX=RAGNAR

# Needed for /api/integrations/* calls from n8n
ADMIN_TOKEN=your-admin-token
```

Restart uvicorn. Check footer `/api/meta` → `integrations.n8n` / `obsidian`.

## 2. Wire n8n

1. Import [`integrations/n8n/ragnar-events.json`](n8n/ragnar-events.json).
2. Open the **Webhook** node → copy **Production URL** → set `N8N_WEBHOOK_URL`.
3. (Recommended) Add an **IF** / **Switch** on `{{$json.event}}`.
4. For Obsidian notes without Local REST API:
   - Use **Write Binary File** / **Read/Write Files** pointing at your vault folder, or
   - Call Obsidian Local REST API from n8n (`PUT /vault/...`).
5. For a full vault refresh on a schedule: HTTP Request  
   `POST {{RAGNAR}}/api/integrations/obsidian/sync`  
   Header `X-Admin-Token: {{ADMIN_TOKEN}}`  
   Then loop `files[]` and write each `path` / `content`.

### Events emitted

| Event | When |
|---|---|
| `listing.created` | New listing posted |
| `order.paid` | Stripe checkout completed |
| `seller.applied` | Seller account created |
| `founding.applied` | Founding 250 application |
| `support.escalated` | Counsel case needs human |
| `knowledge.updated` | Policy/FAQ article changed |
| `knowledge.vault_synced` | Full vault sync requested |
| `ops.alert` | Any ops alert (Discord fan-out twin) |
| `integrations.test` | Manual ping from `/api/integrations/events/test` |

Payload shape:

```json
{
  "event": "order.paid",
  "ts": "2026-07-22T16:00:00+00:00",
  "source": "ragnar",
  "data": { "order_id": 12, "title": "…", "price_cents": 4999 }
}
```

If `N8N_WEBHOOK_SECRET` is set, verify header `X-Ragnar-Signature: sha256=<hmac>`.

## 3. Wire Obsidian

### Install the plugin
Open this in Obsidian (or Community plugins → search **Local REST API**):

`obsidian://show-plugin?id=obsidian-local-rest-api`

Then: **Enable** → **Settings → Local REST API** → copy the **API key**.

| Mode | URL | Notes |
|---|---|---|
| HTTPS (default) | `https://127.0.0.1:27124` | Self-signed cert — RAGNAR skips verify |
| HTTP (optional) | `http://127.0.0.1:27123` | Enable under Settings → Local REST API → **Enable HTTP server** |

### Important: localhost only
The plugin listens on **your computer**. A cloud/Render RAGNAR cannot reach `127.0.0.1` on your desk.

- **Local RAGNAR** (uvicorn on the same machine as Obsidian): set `OBSIDIAN_API_URL` + `OBSIDIAN_API_KEY` and call `POST /api/integrations/obsidian/sync`.
- **Hosted RAGNAR**: keep Obsidian sync in **n8n on your machine** (or any runner that can hit localhost / your vault folder). RAGNAR still emits `knowledge.updated` / `knowledge.vault_synced` to n8n; n8n writes the notes.

### Option A — via n8n (recommended for hosted apps)
n8n receives `knowledge.updated` / vault sync and writes markdown into the vault
path (e.g. `RAGNAR/policy/refund-policy.md`), either with a file Write node or
HTTP → `PUT https://127.0.0.1:27124/vault/...`.

### Option B — Local REST API direct (desktop RAGNAR)
1. Install/enable the plugin (link above).
2. Copy the API key → `OBSIDIAN_API_KEY`.
3. Set `OBSIDIAN_API_URL=https://127.0.0.1:27124`.
4. Call `POST /api/integrations/obsidian/sync` (or edit a knowledge article) —
   notes land under `OBSIDIAN_VAULT_PREFIX/`.

Frontmatter example:

```yaml
---
title: "Refund policy"
slug: "refund-policy"
category: "policy"
tags: ["policy", "refund", "money"]
active: true
source: ragnar
---
```

## 4. Quick test

```bash
curl -X POST http://127.0.0.1:8000/api/integrations/events/test \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ping":true}'

curl http://127.0.0.1:8000/api/integrations/obsidian/export \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

## API map

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/integrations/status` | Config + event list |
| POST | `/api/integrations/events/test` | Fire test event to n8n |
| GET | `/api/integrations/obsidian/export` | Markdown bundle (JSON) |
| POST | `/api/integrations/obsidian/sync` | Push vault + emit to n8n |
| GET | `/api/integrations/lookup/*` | Listing/order/seller/support for workflows |
