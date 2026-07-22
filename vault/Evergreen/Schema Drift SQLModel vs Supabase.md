---
type: evergreen
tags: [platform, schema]
updated: 2026-07-22
---

# Schema Drift SQLModel vs Supabase

Two memory planes until cutover is intentional.

## Live today (product)

- SQLModel + SQLite (`app/models/tables.py`)
- Integer PKs, marketplace + rides + support
- `USE_SUPABASE_DB=false`

## Birdman core (Supabase target)

`supabase/schema.sql` — mirrors FastAPI v1:

| Table | Role |
|---|---|
| `users` | Identity (`auth.users.id`) |
| `content` | Content units |
| `actions` | Interactions / n8n triggers |
| `realtime_events` | SSE / WS payloads |
| `system_logs` | System memory |

See [[Maps/Birdman Supabase Schema]] · [[Evergreen/Birdman Supabase Schema]]

## Cutover rule

1. Apply Birdman core schema in Supabase  
2. Point services at these tables  
3. Layer marketplace domain tables later (or keep SQLModel until migrated)  
4. Only then set `USE_SUPABASE_DB=true`

Credentials can be linked early; data plane flips last.

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Dual Auth Path]]
- [[Evergreen/Birdman FastAPI Structure]]
- [[Projects/Birdman Platform]]
