---
type: template
domain: backend
updated: 2026-07-22
---

# {{title}}

Backend module note. Fill before or with the PR that introduces the module.

## Purpose

One sentence. What flow does this serve?

## Layer

- [ ] FastAPI router
- [ ] FastAPI service (`app/platform` or domain)
- [ ] Supabase schema
- [ ] Redis cache key / queue topic
- [ ] n8n workflow
- [ ] CDN/static

## Public surface

Endpoints, functions, or workflow triggers:

-

## Connections

- Upstream:
- Downstream:
- Events emitted:
- Jobs enqueued:

## Cache / TTL

-

## Failure mode

What happens if Redis / n8n / Supabase is down?

## Related

- [[Maps/Birdman Systems]]
- [[System/Platform Principles]]
- [[Evergreen/Async Boundary]]
