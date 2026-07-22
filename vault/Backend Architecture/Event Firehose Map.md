---
type: map
domain: backend
updated: 2026-07-22
---

# Event Firehose Map

How activity leaves the request path and reaches n8n + Realtime — without a second
copy of the domain.

```
FastAPI service
   │  (best-effort, never blocks the response)
   ├── emit → public.market_events      ─┐
   ├── emit → public.realtime_events     ─┼─→ Supabase Realtime → live UI
   ├── log  → public.system_logs         ─┘   (publication: market_events, realtime_events)
   └── enqueue_job → Redis queue → n8n workflows (background)
```

## Contracts

| Channel | Table / medium | Blocking? | Consumer |
|---|---|---|---|
| Activity feed | `market_events` | no | Realtime, analytics, n8n |
| Live broadcast | `realtime_events` | no | Realtime subscriptions |
| Audit / debug | `system_logs` | no | n8n audit, ops |
| Work | Redis → n8n | no (async boundary) | notifications, rollups, market/daily-analytics |

## Rules

- Append-only. No FKs into the product schema (a stream must not block on truth).
- Service-role writes; RLS gives clients read-only on the two public tables.
- n8n is **never** on the hot path ([[Evergreen/Async Boundary]]).

Related: [[Database Architecture/Telemetry Schema Explanation]] · [[Evergreen/Event Bus as Nervous System]] · [[Maps/Birdman Workflows]]
