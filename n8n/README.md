# Birdman n8n workflows

**Never in the hot path.** FastAPI → Redis queue → webhook fire-and-forget.

```
N8N_WEBHOOK_BASE=https://<n8n-host>/webhook
N8N_SHARED_SECRET=<same as FastAPI>
```

## Categories

| Category | Job `type` | Webhook path | File |
|---|---|---|---|
| Notification | `notification` | `notification/send` | `notification-send.json` |
| Enrichment | `enrich_content` | `enrich/content` | `enrich-content.json` |
| Analytics | `aggregate_actions` | `analytics/aggregate` | `analytics-aggregate.json` |
| Realtime | `broadcast_event` | `realtime/broadcast` | `realtime-broadcast.json` |
| Maintenance | `maintenance` | `maintenance/run` | `maintenance-run.json` |
| Ripple | `user_action_like` | `actions/user-like` | `actions-user-like.json` |

Legacy product topics still map: `ops.notify`, `media.enhance`, `ride.phase_changed`.

## Job payload

```json
{
  "type": "user_action_like",
  "user_id": "uuid",
  "content_id": "uuid",
  "action_type": "like",
  "timestamp": "2026-07-22T13:52:00Z"
}
```

Envelope also includes `id`, `topic`, `workflow`, `payload`, `enqueued_at` from FastAPI.

## Rules

1. Atomic — one clear job per workflow  
2. Composable — bigger flows call smaller ones  
3. Async only — no request waits  
4. Logged — every run writes `system_logs`  
5. Documented — Obsidian note per workflow  

Vault: [[Maps/Birdman Workflows]] · [[Templates/n8n Workflow]] · [[Evergreen/Async Boundary]]
