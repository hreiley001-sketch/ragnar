---
type: map
domain: marketplace
updated: 2026-07-22
---

# Birdman Marketplace Stack

One goal: a living online card marketplace. Same Birdman organism — marketplace domain on top.

```
User (buyer/seller)
  ↓
Frontend (marketplace UI)
  ↓
CDN / Load Balancer
  ↓
FastAPI (users · cards · listings · orders · market-events)
  ↓
Services (business logic)
  ↓
Supabase (cards, listings, orders, market_events)
Redis (cache for reads)
Redis (queue → n8n)
  ↓
n8n (notifications, analytics, integrations)
  ↓
Supabase (market_events, system_logs, market_stats)
  ↓
Realtime (realtime_events → clients)
```

## Layer roles

| Layer | Marketplace job |
|---|---|
| FastAPI | Routes + logic |
| Supabase | Cards, users, listings, trades, events |
| n8n | Notifications, sync, ops |
| Redis | Hot listing cache + job queue |
| Obsidian | Specs + playbooks |
| CDN/LB | Front door for scale |

## Code anchors

- `supabase/schema.sql` — marketplace tables
- `app/api/v1/{cards,listings,orders,market_events,users}.py`
- `app/services/{card,listing,order,market_event}_service.py`
- `app/core/jobs.py` — marketplace job types
- `n8n/workflows/market-*.json`

## Related

- [[Maps/Birdman Systems]]
- [[Maps/Birdman Supabase Schema]]
- [[Maps/Birdman Workflows]]
- [[Architecture/FastAPI Marketplace Modules]]
- [[Architecture/Supabase Marketplace Schema]]
- [[Features/Live Selling]]
- [[Playbooks/Scaling Strategy]]
