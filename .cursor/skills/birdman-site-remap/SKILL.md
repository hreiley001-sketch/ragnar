---
name: birdman-site-remap
description: >-
  Remap and polish the RAGNAR storefront onto the Birdman spine (FastAPI /api/v1,
  services, Redis, Supabase, n8n) without breaking Stripe or cookie auth. Use when
  upgrading pages, dual-writing listings/orders, polishing UI onto birdman.js,
  or continuing the strangler-fig cutover. Always keep Maps/RAGNAR as the hub.
---

# RAGNAR site remap (Birdman body)

## Goal

**One product: RAGNAR.** Birdman is the organism underneath. Storefront stays usable while every domain moves onto the spine.

Hub notes: `vault/Maps/RAGNAR.md` · `docs/RAGNAR_MAP.md` · `AGENTS.md`

```
HTML pages (stable RAGNAR URLs)
  → static/birdman.js
  → /api/v1/* (BFF + market)  with fallback → /api/*
  → app/services/* (logic)
  → SQLModel (truth today) + Supabase mirror (async)
  → Redis cache/queue → n8n
```

## Hard rules

1. User-facing language = **RAGNAR**; stack language = Birdman.
2. **Never** break cookie auth or Stripe checkout/webhook.
3. **Never** point UI at thin UUID `/api/v1/listings` until DTO includes title/image/price.
4. Prefer **`/api/v1/marketplace/browse`** for rich browse.
5. Dual-write via `app/services/market_bridge.py` — best-effort, never raise into hot path.
6. Put search/query logic in `app/services/*`, not routers.
7. Document cutovers in `vault/Playbooks/Site Remap.md` and link [[Maps/RAGNAR]].

## Shared client

`static/birdman.js` → `window.Birdman`: `api`, `browseListings`, `me`, `pulse`, `siteContent`.

## Page upgrade checklist

1. Load `birdman.js` early
2. Prefer Birdman helpers; keep thin fallback
3. Domain must map to a RAGNAR spoke (browse/sell/buy/live/social/trust/ops)
4. Update vault + `knowledge_capture` on substantial waves

## Do not

- Ship a parallel “Birdman” frontend brand
- Flip `USE_SUPABASE_DB` until dual-write proven
- Publish legal without approval
