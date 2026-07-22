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
users (1) ────< cards (many) ────< listings (many) ────< orders (many)
users ········· market_events · market_stats

realtime_events  (by channel)
system_logs      (by source)
```

## Flow

identity → content → interaction → realtime → system memory  
marketplace: card → listing → order → market_events (+ n8n)

## Tables

| Table | One job |
|---|---|
| `users` | Identity + profile (+ buyer/seller/admin) |
| `content` | Content units |
| `actions` | User interactions / triggers |
| `realtime_events` | Broadcast units |
| `system_logs` | System memory |
| `cards` | Collectibles |
| `listings` | Offers to sell |
| `orders` | Purchases |
| `market_events` | Marketplace feed |
| `market_stats` | Daily rollups |

## Mirrors FastAPI

- `api/v1/users` ↔ `users`
- `api/v1/content` ↔ `content`
- `api/v1/actions` ↔ `actions` (+ Redis → n8n)
- `api/v1/realtime` ↔ `realtime_events`
- `api/v1/cards` ↔ `cards`
- `api/v1/listings` ↔ `listings`
- `api/v1/orders` ↔ `orders`
- `api/v1/market-events` ↔ `market_events`

## Code

- `supabase/schema.sql`
- `app/models/` pydantic shapes
- `app/core/database.py` pooler seam
- `app/core/supabase_rest.py` marketplace REST seam

## Links

- [[Architecture/Supabase Marketplace Schema]]
- [[Architecture/Birdman Marketplace Stack]]
- [[Evergreen/Birdman FastAPI Structure]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]
- [[Evergreen/Async Boundary]]
- [[Maps/Birdman Systems]]
- [[Projects/Birdman Platform]]
