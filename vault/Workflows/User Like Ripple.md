---
type: workflow
category: ripple
updated: 2026-07-22
---

# User Like Ripple

## Trigger

- [x] FastAPI webhook (fire-and-forget via Redis enqueue)
- Job type: `user_action_like`
- Path: `actions/user-like`
- Endpoint: `POST /api/v1/actions/like`

## Inputs

```json
{
  "type": "user_action_like",
  "user_id": "uuid",
  "content_id": "uuid",
  "action_type": "like",
  "timestamp": "ISO-8601"
}
```

## Steps

1. Normalize job  
2. Update content_stats (likes)  
3. Insert `realtime_events` (`content_liked`)  
4. Write `system_logs`  

## Outputs / side effects

- `realtime_events` row for subscribed clients  
- `system_logs` audit  
- Future: `content_stats.likes`  

## Failure modes

- Missing `content_id` → log error, no broadcast  
- Supabase write fail → retry once, then `system_logs` level=error  
- FastAPI already returned 202 — user never blocked  

## Related

- [[Maps/Birdman Workflows]]
- [[Maps/Birdman Supabase Schema]]
- [[Evergreen/Async Boundary]]
- `n8n/workflows/actions-user-like.json`
