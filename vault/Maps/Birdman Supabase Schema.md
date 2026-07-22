---
type: map
domain: data
updated: 2026-07-22
---

# Birdman Supabase Schema

The memory layer. Atomic. Linked. Intentional.

```
users (1) ────< content (many)
users (1) ────< actions (many)
content (1) ────< actions (many)

realtime_events  (by channel)
system_logs      (by source)
```

## Flow

identity → content → interaction → realtime → system memory

## Tables

| Table | One job |
|---|---|
| `users` | Identity + profile |
| `content` | Content units |
| `actions` | User interactions / triggers |
| `realtime_events` | Broadcast units |
| `system_logs` | System memory |

## Mirrors FastAPI

- `api/v1/users` ↔ `users`
- `api/v1/content` ↔ `content`
- `api/v1/actions` ↔ `actions` (+ Redis → n8n)
- `api/v1/realtime` ↔ `realtime_events`

## Code

- `supabase/schema.sql`
- `app/models/` pydantic shapes
- `app/core/database.py` pooler seam

## Links

- [[Evergreen/Birdman FastAPI Structure]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]
- [[Evergreen/Async Boundary]]
- [[Maps/Birdman Systems]]
- [[Projects/Birdman Platform]]
