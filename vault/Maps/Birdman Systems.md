---
type: map
domain: infrastructure
updated: 2026-07-22
---

# Birdman Systems

The platform organism. Product mind ([[Maps/BirdmanOS]]) rides on this body.

## Essence

One cohesive backend: FastAPI thinks, Supabase remembers, Redis remembers briefly, n8n acts in the background, CDN/LB carries traffic, Obsidian designs before code.

```
Edge (CDN + LB)
    ↓
FastAPI nodes (stateless, async)
    ├── Redis  — cache + job queue
    ├── Supabase — data + JWT auth + realtime
    └── n8n   — automation (never hot path)
```

## Layer contracts

| Layer | Job | Never |
|---|---|---|
| FastAPI | Logic, APIs, orchestration | Sync waits on n8n |
| Supabase | Durable truth + auth | Hot-path automation |
| Redis | Short memory + queues | Source of truth |
| n8n | Background workflows | Request latency budget |
| CDN/LB | Traffic + static | Business logic |
| Obsidian | System mindspace | Runtime dependency |

## Module anchors (code)

- `app/core/` — spine (config, security, cache, queue, database)
- `app/api/v1/` — thin versioned surface
- `app/services/` — flow engine
- `app/models/` — SQLModel tables + pydantic map
- `app/utils/` — smoothness
- `supabase/schema.sql` — Birdman core + marketplace memory (users · cards · listings · orders · events)
- [[Maps/Birdman Supabase Schema]]
- [[Architecture/Birdman Marketplace Stack]]
- `n8n/workflows/` — modular automations (incl. `market-*`)
- `docs/BIRDMAN_ARCHITECTURE.md` — diagram + edge notes
- `GET /api/v1/realtime/pulse` · `GET /api/platform/status` — organ health
- [[Evergreen/Birdman FastAPI Structure]]
- [[Architecture/FastAPI Marketplace Modules]]

## Knowledge links

- [[Evergreen/Event Bus as Nervous System]]
- [[Evergreen/Platform as One Organism]]
- [[Evergreen/Async Boundary]]
- [[Evergreen/Dual Auth Path]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]
- [[Evergreen/Cache Keys and TTLs]]
- [[Features/Live Selling]]
- [[Playbooks/Scaling Strategy]]
- [[Maps/BirdmanOS]]
- [[Maps/RAGNAR]]
- [[System/Platform Principles]]
- [[Projects/Birdman Platform]]
## Open questions

- ~~Migrate session cookies → Supabase JWT gradually or cut over?~~ → [[Evergreen/Dual Auth Path]] (both, gradual)
- Which reads deserve Redis first: listings search, ride state, catalog? → listings done; see [[Evergreen/Cache Keys and TTLs]]
- Schema cutover: keep [[Evergreen/Schema Drift SQLModel vs Supabase]] until Alembic aligns

## Live credentials

Supabase project linked in local `.env` (URL, anon, secret, JWT, pooler). `USE_SUPABASE_DB=false` until schema cutover.
