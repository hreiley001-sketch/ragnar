---
type: project
status: active
updated: 2026-07-22
---

# Birdman Platform

## Outcome

A unified backend organism — FastAPI · Supabase · Redis · n8n · CDN/LB — wired with Obsidian as the design mindspace. Cohesive, minimal, horizontally scalable.

## Why

Product logic (BirdmanOS) needs a body that scales without fragmenting: cache, async automation, JWT data plane, edge traffic.

## Current focus

- [x] Obsidian architecture maps + templates
- [x] `app/platform/` (redis, cache, queue, n8n, supabase)
- [x] Event bus → async enqueue boundary
- [x] Supabase schema + n8n workflow stubs
- [x] `/api/platform/status` + docs
- [x] Link live Supabase credentials (URL / keys / JWT / pooler)
- [x] Dual auth (cookie + Supabase Bearer JWT)
- [x] Cache listings search + site-config
- [x] Enqueue media.enhance + ops.notify
- [x] Birdman FastAPI folder spine (`core` / `api/v1` / `services` / `models` / `utils`)
- [ ] Provision Redis + n8n in staging
- [ ] Reconcile SQLModel ↔ Supabase schema (then `USE_SUPABASE_DB=true`)
- [ ] Cache ride state / catalog (tiny TTLs)
- [ ] Migrate marketplace routers into `api/v1` + services gradually

## Linked ideas

- [[Maps/Birdman Systems]]
- [[System/Platform Principles]]
- [[Evergreen/Async Boundary]]
- [[Evergreen/Dual Auth Path]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]
- [[Evergreen/Cache Keys and TTLs]]
- [[Evergreen/Platform as One Organism]]
- [[Maps/BirdmanOS]]

## Next move

Set `REDIS_URL` + `N8N_WEBHOOK_BASE` in staging; import `n8n/workflows/`; confirm `GET /api/platform/status`.
