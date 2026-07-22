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
| Marketplace | `listing_created` | [[Workflows/Listing Created]] |
| Marketplace | `order_placed` | [[Workflows/Order Placed]] |
| Marketplace | `order_status_changed` | [[Workflows/Order Status Changed]] |
| Marketplace | `buyer_notification` / `seller_notification` | [[Workflows/Buyer Notification]] · [[Workflows/Seller Notification]] |
| Marketplace | `market_daily_analytics` | [[Workflows/Daily Marketplace Analytics]] |

## Design rules

1. Atomic — one clear thing  
2. Composable — small workflows build larger ones  
3. Async only  
4. Logged → `system_logs`  
5. Documented — every workflow has an Obsidian note  

## Code

- `app/core/jobs.py` — envelope + type → path map  
- `app/services/action_service.py` — enqueue helpers  
- `app/services/{listing,order}_service.py` — marketplace enqueue  
- `POST /api/v1/actions/like` — like ripple entry  
- `n8n/workflows/` — importable stubs (`market-*.json`)  
- [[Architecture/n8n Marketplace Catalog]]

## Links

- [[Evergreen/Async Boundary]]
- [[Maps/Birdman Systems]]
- [[Architecture/Birdman Marketplace Stack]]
- [[Maps/Birdman Supabase Schema]]
- [[Evergreen/Birdman FastAPI Structure]]
- [[Templates/n8n Workflow]]
- [[Projects/Birdman Platform]]
