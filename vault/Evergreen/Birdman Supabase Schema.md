---
type: evergreen
tags: [platform, schema]
updated: 2026-07-22
---

# Birdman Supabase Schema

Core memory tables — deploy via `supabase/schema.sql`.

## Principles

1. Atomic tables — one concept each  
2. Clean relationships — predictable FKs  
3. JSONB for flexible metadata  
4. Index what scales (`email`, `author_id`, `action_type`, `channel`, GIN on metadata)  
5. Schema mirrors FastAPI modules  

## Cutover

1. Run `schema.sql` in Supabase SQL editor  
2. Keep `USE_SUPABASE_DB=false` until services read/write these tables  
3. Marketplace SQLModel remains live product DB until domain layer is added  

## Links

- [[Maps/Birdman Supabase Schema]]
- [[Evergreen/Birdman FastAPI Structure]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]
- [[Projects/Birdman Platform]]
