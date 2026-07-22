---
type: map
domain: automation
updated: 2026-07-22
---

# Birdman Workflows

Clean triggers. Async muscles. Everything flows.

```
FastAPI (event source)
  ↓ writes intent
Supabase (structured truth)
  ↓ enqueue
Redis queue (buffer)
  ↓ fire-and-forget
n8n (modular workflows)
  ↓ results / logs
Supabase (system_logs · realtime_events · content)
```

**Rule:** FastAPI never blocks on n8n.

## Categories

| Category | Job type | Spec |
|---|---|---|
| Notification | `notification` | [[Workflows/Notification Send]] |
| Enrichment | `enrich_content` | [[Workflows/Enrich Content]] |
| Analytics | `aggregate_actions` | [[Workflows/Aggregate Actions]] |
| Realtime | `broadcast_event` | [[Workflows/Realtime Broadcast]] |
| Maintenance | `maintenance` | [[Workflows/Maintenance Run]] |
| Ripple | `user_action_like` | [[Workflows/User Like Ripple]] |

## Design rules

1. Atomic — one clear thing  
2. Composable — small workflows build larger ones  
3. Async only  
4. Logged → `system_logs`  
5. Documented — every workflow has an Obsidian note  

## Code

- `app/core/jobs.py` — envelope + type → path map  
- `app/services/action_service.py` — enqueue helpers  
- `POST /api/v1/actions/like` — like ripple entry  
- `n8n/workflows/` — importable stubs  

## Links

- [[Evergreen/Async Boundary]]
- [[Maps/Birdman Systems]]
- [[Maps/Birdman Supabase Schema]]
- [[Evergreen/Birdman FastAPI Structure]]
- [[Templates/n8n Workflow]]
- [[Projects/Birdman Platform]]
