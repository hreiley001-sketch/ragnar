---
type: skill
domain: marketplace
updated: 2026-07-22
---

# Skill — Dual-Write Bridge

> [!warning] Superseded by single-write.
> The migration ([[Supabase Migration/Migration Plan]]) makes Supabase Postgres the
> single source of truth, so the dual-write of domain rows is **retired**. `market_bridge`
> becomes single-write + event **emit** — see [[Backend Architecture/Service Flow Diagrams]]
> and [[Backend Architecture/REST Endpoint Retirement]]. Kept as the record of the
> transitional pattern.

SQLModel stayed truth until cutover; Birdman memory stayed warm via best-effort mirror.

## Pattern

1. Complete the legacy write (listing create, Stripe paid, ship).
2. Call `market_bridge` best-effort — never raise into the request.
3. Enqueue n8n job types from `app/core/jobs.py`.
4. Invalidate Redis keys for that domain.

## Anchors

- `app/services/market_bridge.py`
- Listing create → `mirror_listing_created`
- Stripe paid → `mirror_order_paid`
- [[Evergreen/Async Boundary]]
- [[Skills/Birdman Storefront Remap]]

## Win condition

Hot path latency unchanged; Supabase/n8n receive mirrors when configured.
