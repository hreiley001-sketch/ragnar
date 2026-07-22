---
type: skill
domain: marketplace
updated: 2026-07-22
---

# Skill — Dual-Write Bridge

SQLModel stays truth until cutover. Birdman memory stays warm.

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
