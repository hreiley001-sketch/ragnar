---
type: feature
domain: marketplace
updated: 2026-07-22
---

# Live Selling

Realtime layer for live marketplace moments.

- Write intent via FastAPI → `realtime_events` / `market_events`
- Broadcast via n8n `broadcast_event` or Supabase Realtime
- Clients subscribe SSE/WS (`api/v1/realtime`)
- Hot reads: Redis `market:listings:active`, `market:feed`

Scale path: [[Playbooks/Scaling Strategy]]
