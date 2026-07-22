---
name: birdman-site-remap
description: >-
  Remap RAGNAR storefront onto the Birdman spine (FastAPI /api/v1, services,
  Redis, Supabase, n8n) without breaking Stripe or cookie auth. Use when
  upgrading pages, dual-writing listings/orders, polishing static UI onto
  birdman.js, or continuing the strangler-fig cutover from legacy /api/*.
---

# Birdman Site Remap

## Goal

One organism: storefront stays usable while every domain moves onto Birdman.

```
HTML pages (stable URLs)
  → static/birdman.js
  → /api/v1/* (BFF + market)  with fallback → /api/*
  → app/services/* (logic)
  → SQLModel (truth today) + Supabase REST mirror (async)
  → Redis cache/queue → n8n
```

## Hard rules

1. **Never** break cookie auth or Stripe checkout/webhook.
2. **Never** point UI at thin UUID `/api/v1/listings` until DTO includes title/image/price.
3. Prefer **`/api/v1/marketplace/browse`** for rich browse (storefront ListingPage).
4. Dual-write via `app/services/market_bridge.py` — best-effort, never raise into hot path.
5. Put search/query logic in `app/services/*`, not routers.
6. Document every cutover step in `vault/Playbooks/Site Remap.md`.

## Shared client

`static/birdman.js` exposes `window.Birdman`:

- `api(path, opts)` — credentials same-origin
- `browseListings(params)` — v1 browse → legacy fallback
- `me()` — v1 profile → `/api/auth/me` fallback
- `pulse()` — marketplace/realtime/platform pulse
- `siteContent()` — v1 content/site → site-config fallback

Load it before page scripts. `nav.js` also injects it if missing.

## Page upgrade checklist

When touching a static page:

1. Ensure `<script src="/static/birdman.js"></script>` early
2. Replace local `api()` with `Birdman.api` (keep thin fallback)
3. Prefer `Birdman.browseListings` / `Birdman.me` / `Birdman.pulse` where relevant
4. Do not remove legacy endpoints until dual-write proven

## Backend checklist

1. New reads → service + `/api/v1/...` BFF if storefront-shaped
2. New writes → legacy contract + `market_bridge` mirror
3. Invalidate Redis keys used by that domain
4. Enqueue n8n job types from `app/core/jobs.py`
5. Add/extend tests in `tests/test_birdman_api.py`

## Obsidian lock-in

After each wave, update:

- `vault/Playbooks/Site Remap.md` — what landed / still open
- `vault/Skills/*` — reusable pattern notes
- `vault/Maps/Birdman Systems.md` — anchors
- Sync important notes to Valhalla when possible

## Do not

- Commit nested `/ragnar/` or `.env`
- Flip `USE_SUPABASE_DB=true` until schema applied + dual-write healthy
- Rewrite all CSS at once — consolidate sheet-by-sheet
