---
type: playbook
domain: marketplace
updated: 2026-07-22
---

# Scaling Strategy

For 100k+ viewers on live marketplace:

1. **CDN/LB** — static + edge terminate TLS  
2. **Read path** — Redis for listings + feed; Supabase read replicas later  
3. **Write path** — FastAPI → Supabase → Redis jobs (never sync n8n)  
4. **Realtime** — `realtime_events` / SSE; fan-out via Redis pubsub or Supabase Realtime  
5. **Hot events** — price changes, new listings, live selling, chat as event types  

Keep business logic in FastAPI services; automation stays async.
